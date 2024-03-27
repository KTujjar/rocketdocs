import asyncio
import json
import os
from typing import Coroutine, List, Any, Dict, Optional
from collections import defaultdict

import firebase_admin
import marko
from bs4 import BeautifulSoup
from github.ContentFile import ContentFile
from marko.block import Heading
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletion

from schemas.documentation_generation import (
    StatusEnum,
    GeneratedDoc,
    LlmModelEnum,
    FirestoreDoc,
    FirestoreRepo,
    FirestoreDocType,
    LlmProvider,
    LlmJsonResponse,
)
from services.clients.anyscale_client import get_anyscale_client
from services.clients.openai_client import get_openai_client
from services.data_service import DataService, get_data_service
from services.rag_service.embedding_service import EmbeddingService, get_embedding_service
from fastapi import BackgroundTasks, HTTPException, status
from transformers import AutoTokenizer

from dotenv import load_dotenv

from services.clients.llm_client import LLMClient
from services.github_service import GithubService, get_github_service
from services._prompts import (
    ONE_SHOT_FILE_SYS_PROMPT,
    NO_SHOT_FILE_JSON_SYS_PROMPT,
    NO_SHOT_FOLDER_JSON_SYS_PROMPT,
    ONE_SHOT_FOLDER_SYS_PROMPT,
)


class DocumentationService:
    def __init__(
        self,
        llm_client: LLMClient,
        github_service: GithubService,
        data_service: DataService,
        embedding_service: EmbeddingService,
    ):
        self.llm_client = llm_client
        self.github_service = github_service
        self.data_service = data_service
        self.embedding_service = embedding_service
        self.tokenizer = AutoTokenizer.from_pretrained("mistralai/Mixtral-8x7B-Instruct-v0.1")
        self.system_prompt_for_file_json = NO_SHOT_FILE_JSON_SYS_PROMPT
        self.system_prompt_for_folder_json = NO_SHOT_FOLDER_JSON_SYS_PROMPT
        self.system_prompt_for_folder_markdown = ONE_SHOT_FOLDER_SYS_PROMPT
        self.system_prompt_for_file_markdown = ONE_SHOT_FILE_SYS_PROMPT

    async def generate_doc(
        self, doc_id: str, model: LlmModelEnum, dependencies: Optional[List[str]] = None
    ):
        if dependencies is None:
            dependencies = []

        doc = self.data_service.get_documentation(doc_id)
        dep_docs = [self.data_service.get_documentation(dep) for dep in dependencies]
        self._validate_doc_and_dependencies(doc, dep_docs)

        self.data_service.update_documentation(
            doc_id, FirestoreDoc(status=StatusEnum.IN_PROGRESS)
        )

        try:
            if doc.type == FirestoreDocType.FILE:
                file_content = self.github_service.get_file_from_url(doc.github_url)
                generated_doc = await self._generate_doc_for_file(file_content, model)
            elif doc.type == FirestoreDocType.DIRECTORY:
                generated_doc = await self._generate_doc_for_folder(
                    doc, dep_docs, model
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Doc type not supported",
                )
        except Exception as e:
            self.data_service.update_documentation(
                doc.id, FirestoreDoc(status=StatusEnum.FAILED)
            )
            raise e

        self.data_service.update_documentation(
            doc_id,
            FirestoreDoc(
                extracted_data=generated_doc.extracted_data,
                markdown_content=generated_doc.markdown_content,
                usage=generated_doc.usage,
                status=StatusEnum.COMPLETED,
            ),
        )

    def generate_file_doc_background_task(
        self, doc_id: str, model: LlmModelEnum
    ) -> None:
        generated_doc = asyncio.run(self.generate_doc(doc_id, model))

        self.data_service.update_documentation(
            doc_id,
            FirestoreDoc(
                extracted_data=generated_doc.extracted_data,
                markdown_content=generated_doc.markdown_content,
                usage=generated_doc.usage,
                status=StatusEnum.COMPLETED,
            ),
        )

    # background tasks for generating the documentation
    def enqueue_generate_file_doc_job(
        self,
        user_id: str,
        background_tasks: BackgroundTasks,
        file: ContentFile,
        model: LlmModelEnum,
    ) -> str:
        doc_id = self.data_service.add_documentation(
            FirestoreDoc(
                github_url=file.html_url,
                type=file.type,
                size=file.size,
                relative_path=file.path,
                status=StatusEnum.IN_PROGRESS,
                owner=user_id,
            )
        )

        # add task to be done async
        background_tasks.add_task(self.generate_file_doc_background_task, doc_id, model)

        return doc_id

    async def generate_repo_docs(
        self, firestore_repo: FirestoreRepo, model: LlmModelEnum
    ) -> None:
        self._validate_repo(firestore_repo)

        dgraph = firestore_repo.dependencies
        root = firestore_repo.root_doc

        children_graph = {parent: [] for parent in dgraph.values()}
        indegree = defaultdict(int, {node: 0 for node in dgraph})

        for child, parent in dgraph.items():
            if parent:
                children_graph[parent].append(child)
                indegree[parent] += 1

        while root in indegree:
            leaves = [node for node, degree in indegree.items() if degree == 0]
            tasks = [
                self.generate_doc(leaf, model, children_graph.get(leaf))
                for leaf in leaves
            ]

            results = await self._run_concurrently(tasks, 30)
            for result in results:
                if isinstance(result, BaseException):
                    self.data_service.update_repo(
                        firestore_repo.id, FirestoreRepo(status=StatusEnum.FAILED)
                    )
                    raise result

            for leaf in leaves:
                parent = dgraph[leaf]
                if parent:
                    indegree[parent] -= 1
                indegree.pop(leaf)

        self.data_service.update_repo(
            firestore_repo.id, FirestoreRepo(status=StatusEnum.COMPLETED)
        )

    async def generate_repo_docs_and_embed_background_task(
            self,
            firestore_repo: FirestoreRepo,
            model: LlmModelEnum,
            user_id: str,
    ):
        self.data_service.update_repo(
            firestore_repo.id, FirestoreRepo(status=StatusEnum.IN_PROGRESS)
        )
        await self.generate_repo_docs(firestore_repo, model)
        await self.embedding_service.generate_markdown_embeddings_for_repo(firestore_repo.id, user_id)

    def regenerate_doc(
        self,
        background_tasks: BackgroundTasks,
        user_id: str,
        doc_id: str,
        model: LlmModelEnum,
    ) -> str:
        doc = self.data_service.get_documentation(doc_id)
        if doc.status not in [StatusEnum.COMPLETED, StatusEnum.FAILED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Data is still being generated for this id, so it cannot be regenerated yet.",
            )

        github_file = self.github_service.get_file_from_url(doc.github_url)

        self.data_service.update_documentation(
            doc_id,
            FirestoreDoc(
                id=doc_id,
                owner=user_id,
                github_url=github_file.html_url,
                type=github_file.type,
                size=github_file.size,
                relative_path=github_file.path,
                status=StatusEnum.IN_PROGRESS,
            ),
        )

        background_tasks.add_task(self.generate_file_doc_background_task, doc_id, model)

        return doc_id

    async def _generate_doc_for_file(
        self, file: ContentFile, model: LlmModelEnum
    ) -> GeneratedDoc:
        if not file or file.type != FirestoreDocType.FILE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="File cannot be empty"
            )
        
        file_content = file.decoded_content.decode("utf-8")
        token_count = len(self.tokenizer.encode(file_content))
        # 32k token limit
        # ~850 for system prompt
        # 2048 for max input
        # With margin of error, we limit token count to 28k tokens.
        if token_count > 28000:
            extra_tokens = token_count - 28000
            # Assume 4 chars = 1 token
            estimated_chars = extra_tokens * 4
            file_content = file_content[:len(file_content) - estimated_chars]
            while len(self.tokenizer.encode(file_content)) > 28000:
                # Delete 400 chars ~ 100 tokens
                file_content = file_content[:len(file_content) - 400]
            file_content += "\n..."
        
        user_prompt_markdown = f"Document the following code file titled {file.path}\n\n{file_content}"
        return await self._generate_doc_with_fallback(
            model, user_prompt_markdown, self.system_prompt_for_file_markdown, file.path
        )

    async def _generate_doc_for_folder(
        self, folder: FirestoreDoc, files: List[FirestoreDoc], model: LlmModelEnum
    ) -> GeneratedDoc:
        self._validate_folder_and_files(folder, files)

        folder_path = 'the root folder' if not folder.relative_path else folder.relative_path
        file_info_list = '\n'.join([f"{i+1}. `{file.relative_path}`: {file.extracted_data.get('description')}" for i, file in enumerate(files)])
        user_prompt_markdown = f"The folder I need documented is {folder_path}. It contains the following files/folders:\n{file_info_list}"
        return await self._generate_doc_with_fallback(
            model,
            user_prompt_markdown,
            self.system_prompt_for_folder_markdown,
            folder.relative_path,
        )

    async def _generate_doc_with_fallback(
        self, model, user_prompt, system_prompt, path
    ):
        total_usage = {
            "completion_tokens": 0,
            "prompt_tokens": 0,
            "total_tokens": 0,
        }
        json_content = None

        markdown_content = await self.llm_client.generate_text(
            model=model,
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.4,
            max_tokens=2048,
        )
        total_usage = self._combine_usage(total_usage, markdown_content.usage)
        markdown_content = self._validate_llm_markdown_response(markdown_content)

        # If we fail to generate JSON, take the description from the Markdown
        if not json_content:
            description = self._extract_first_heading_content(markdown_content)
            if not description:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to generate Markdown content",
                )
            json_content = {"description": description}

        return GeneratedDoc(
            relative_path=path,
            usage=CompletionUsage(**total_usage),
            extracted_data=json_content,
            markdown_content=markdown_content,
        )

    @staticmethod
    def _validate_llm_json_response(
        llm_json_response: LlmJsonResponse,
    ) -> LlmJsonResponse:
        if llm_json_response.finish_reason == "length":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LLM output hit max_token limit",
            )

        return llm_json_response

    @staticmethod
    def _validate_llm_markdown_response(markdown_completion: ChatCompletion) -> str:
        content = markdown_completion.choices[0].message.content
        # rough fix for the bug where the first character is a space, seems to be an Anyscale thing
        if content[0] == " ":
            return content[1:]
        return content

    @staticmethod
    def _validate_folder_and_files(
        folder: FirestoreDoc, files: List[FirestoreDoc]
    ) -> None:
        if not folder or folder.type != FirestoreDocType.DIRECTORY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Folder cannot be empty"
            )
        for file in files:
            if file.status != StatusEnum.COMPLETED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Files are still being generated",
                )

    @staticmethod
    def _validate_doc_and_dependencies(
        parent: FirestoreDoc, dependencies: List[FirestoreDoc]
    ) -> None:
        if parent.type == FirestoreDocType.DIRECTORY and not dependencies:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Dependencies cannot be empty",
            )
        for dep in dependencies:
            if dep.status != StatusEnum.COMPLETED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Dependencies are not completed yet.",
                )

    @staticmethod
    def _validate_repo(repo: FirestoreRepo) -> None:
        if not repo.dependencies or not repo.root_doc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repo does not have a root or dependencies.",
            )

        if repo.status == StatusEnum.IN_PROGRESS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repo is already in progress.",
            )

    @staticmethod
    def _validate_json(json_string: str) -> Dict[str, Any] | None:
        try:
            parsed_json = json.loads(json_string)
            return parsed_json
        except json.JSONDecodeError:
            return None

    @staticmethod
    async def _run_concurrently(
        coroutines: List[Coroutine], batch_size: Optional[int] = None
    ) -> tuple[BaseException | Any]:
        """This method leverages the asyncio library to run Coroutines concurrently.
        :returns: an ordered tuple with the results of the coroutines, including exceptions
        """
        if batch_size:
            results = []
            for i in range(0, len(coroutines), batch_size):
                batch = coroutines[i : i + batch_size]
                results.extend(await asyncio.gather(*batch, return_exceptions=True))
            return tuple(results)
        else:
            return await asyncio.gather(*coroutines, return_exceptions=True)

    @staticmethod
    def _combine_usage(total: Dict[str, int], addition: CompletionUsage):
        total["completion_tokens"] += addition.completion_tokens
        total["prompt_tokens"] += addition.prompt_tokens
        total["total_tokens"] += addition.total_tokens
        return total

    @staticmethod
    def _extract_first_heading_content(markdown_content: str) -> str:
        parsed = marko.parse(markdown_content)
        heading_content = []

        for child in parsed.children:
            if isinstance(child, Heading):
                if not heading_content:  # Skip the first heading
                    continue
                else:
                    break
            html_output = marko.render(child)
            text = BeautifulSoup(html_output, "html.parser").get_text()
            heading_content.append(text)

        return "".join(heading_content)


def get_documentation_service(
    model: LlmModelEnum = LlmModelEnum.MIXTRAL,
) -> DocumentationService:
    """Initializes the service with any dependencies it needs."""
    if model.belongs_to() == LlmProvider.OPENAI:
        llm_client = get_openai_client()
    elif model.belongs_to() == LlmProvider.ANYSCALE:
        llm_client = get_anyscale_client()
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Model provider not supported",
        )

    github_service = get_github_service()
    data_service = get_data_service()
    embedding_service = get_embedding_service()
    return DocumentationService(llm_client, github_service, data_service, embedding_service)


# For manually testing this file
if __name__ == "__main__":
    load_dotenv()
    firebase_app = firebase_admin.initialize_app(
        credential=None, options={"storageBucket": os.getenv("CLOUD_STORAGE_BUCKET")}
    )
    service = get_documentation_service(LlmModelEnum.MIXTRAL)
    github = get_github_service()
    test_file = github.get_file_from_url(
        "https://github.com/cs-discord-at-ucf/lion/blob/master/src/app/__generated__/cat-breeds.json"
    )

    test_result = asyncio.run(
        service._generate_doc_for_file(test_file, LlmModelEnum.MIXTRAL)
    )
    print(test_result)
