import asyncio
import json
import os
from typing import Coroutine, List, Any, Dict
from collections import deque

import firebase_admin
from github.ContentFile import ContentFile
from openai.types.chat import ChatCompletion

from schemas.documentation_generation import DocStatusEnum, \
    GeneratedDoc, LlmModelEnum, LlmDocSchema, RepoFormatted, \
    ReposResponseModel, FirestoreDoc, FirestoreRepo
from services.clients.anyscale_client import get_anyscale_client
from services.data_service import DataService, get_data_service
from fastapi import BackgroundTasks, HTTPException, status

from dotenv import load_dotenv

from services.clients.llm_client import LLMClient
from services.github_service import GithubService, get_github_service


class DocumentationService:
    def __init__(self, llm_client: LLMClient, github_service: GithubService, data_service: DataService):
        self.llm_client = llm_client
        self.github_service = github_service
        self.data_service = data_service
        self.system_prompt_for_file_json = ("You are a helpful assistant that generates "
                                            "high-level documentation of code. Respond in JSON.")

    async def generate_doc_for_file(
            self,
            file: ContentFile,
            model: LlmModelEnum
    ) -> GeneratedDoc:
        if not file:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="File cannot be empty")

        user_prompt = f"{file.path}:\n" + str(file.decoded_content)
        llm_completion = await self._generate_doc_completion(model, user_prompt)
        json_content = self._parse_and_validate_llm_completion(llm_completion)

        markdown_content = await self._generate_markdown_content(model, json_content)

        response = GeneratedDoc(
            relative_path=file.path,
            usage=llm_completion.usage,
            extracted_data=json_content,
            markdown_content=markdown_content
        )

        return response

    # background tasks for generating the documentation
    def generate_doc_background_task(
            self,
            doc_id: str,
            file: ContentFile,
            model: LlmModelEnum
    ) -> None:
        generated_doc = asyncio.run(self.generate_doc_for_file(file, model))

        self.data_service.update_documentation(
            doc_id,
            FirestoreDoc(
                extracted_data=generated_doc.extracted_data,
                markdown_content=generated_doc.markdown_content,
                usage=generated_doc.usage,
                status=DocStatusEnum.COMPLETED,
            ).model_dump(exclude_defaults=True)
        )

    def enqueue_generate_doc_job(
            self,
            user_id: str,
            background_tasks: BackgroundTasks,
            file: ContentFile,
            model: LlmModelEnum
    ) -> str:
        doc_id = self.data_service.add_documentation(
            FirestoreDoc(
                github_url=file.html_url,
                type=file.type,
                size=file.size,
                relative_path=file.path,
                status=DocStatusEnum.IN_PROGRESS,
                owner=user_id
            ).model_dump()
        )

        # add task to be done async
        background_tasks.add_task(
            self.generate_doc_background_task,
            doc_id,
            file,
            model
        )

        return doc_id

    def regenerate_doc(
            self,
            background_tasks: BackgroundTasks,
            user_id: str,
            doc_id: str,
            model: LlmModelEnum
    ) -> str:
        firestore_doc:FirestoreDoc = self.data_service.get_user_documentation(user_id, doc_id)

        if firestore_doc.status not in [DocStatusEnum.COMPLETED, DocStatusEnum.FAILED]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Data is still being generated for this id, so it cannot be regenerated yet.")

        github_file = self.github_service.get_file_from_url(firestore_doc.github_url)

        self.data_service.update_documentation(
            doc_id,
            FirestoreDoc(
                id=doc_id,
                owner=user_id,
                github_url=github_file.html_url,
                type=github_file.type,
                size=github_file.size,
                relative_path=github_file.path,
                status=DocStatusEnum.IN_PROGRESS
            ).model_dump()
        )

        background_tasks.add_task(
            self.generate_doc_background_task,
            doc_id,
            github_file,
            model
        )

        return doc_id

    async def _generate_doc_completion(self, model: LlmModelEnum, prompt: str) -> ChatCompletion:
        return await self.llm_client.generate_json(
            model=model,
            prompt=prompt,
            system_prompt=self.system_prompt_for_file_json,
            response_schema=LlmDocSchema.model_json_schema(),
            max_tokens=2048
        )

    async def _generate_markdown_content(self, model: LlmModelEnum, json_content: dict) -> str:
        prompt = json.dumps(json_content)
        system_prompt = "Your job is to format received input into neat documentation. Respond in Markdown text."

        markdown_llm_completion = await self.llm_client.generate_text(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=2048
        )

        markdown_text = markdown_llm_completion.choices[0].message.content

        # rough fix for the bug where the first character is a space, seems to be an Anyscale thing
        if markdown_text[0] == " ":
            return markdown_text[1:]

        return markdown_text

    def _parse_and_validate_llm_completion(self, llm_completion: ChatCompletion) -> Dict[str, Any]:
        if llm_completion.choices[0].finish_reason == "length":
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="LLM output hit max_token limit")

        json_content = self._parse_json(llm_completion.choices[0].message.content)
        return json_content

    @staticmethod
    def _parse_json(json_string: str) -> Dict[str, Any]:
        try:
            parsed_json = json.loads(json_string)
            return parsed_json
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="LLM output not parsable")
    
    @staticmethod
    def format_repo(repo_response: FirestoreRepo) -> RepoFormatted:
        root_doc: str = repo_response.root_doc
        repo_name: str = repo_response.repo_name
        repo_id: str = repo_response.id
        owner_id: str = repo_response.owner
        dependencies: dict[str, str] = repo_response.dependencies
        docs: list[FirestoreDoc] = repo_response.docs

        repo_formatted = RepoFormatted(name=repo_name, id=repo_id, owner_id=owner_id, tree=[], nodes_map={})

        def find_doc_by_id(doc_list: list[FirestoreDoc], doc_id) -> FirestoreDoc | None:
            for doc in doc_list:
                if doc.id == doc_id: 
                    return doc
            return None

        def process_node(parent_id, child_id):
            parent_data: FirestoreDoc = find_doc_by_id(docs, parent_id)
            child_data: FirestoreDoc = find_doc_by_id(docs, child_id)

            repo_formatted.insert_node(parent_data, child_data)
       
        def bfs(root):
            used = set()

            if not root:
                return
            
            queue = deque([root])

            while queue:
                node = queue.popleft()
                for child, parent in dependencies.items():
                    if parent == node and child not in used:
                        process_node(parent, child)
                        queue.append(child)
                        used.add(child)

        bfs(root_doc)

        return repo_formatted

    @staticmethod
    def get_repo_status(repo_response: FirestoreRepo) -> list[dict[str, DocStatusEnum]]:
        docs = repo_response.docs

        repo_status = [{doc.id: doc.status} for doc in docs]
        return repo_status

    @staticmethod
    def _validate_json(json_string: str) -> Dict[str, Any] | None:
        try:
            parsed_json = json.loads(json_string)
            return parsed_json
        except json.JSONDecodeError:
            return None

    @staticmethod
    async def _run_concurrently(coroutines: List[Coroutine]) -> tuple[BaseException | Any]:
        """This method leverages the asyncio library to run Coroutines concurrently.
        :returns: an ordered tuple with the results of the coroutines, including exceptions
        """
        tasks = []
        for coroutine in coroutines:
            tasks.append(asyncio.ensure_future(coroutine))
        return await asyncio.gather(*tasks, return_exceptions=True)


def get_documentation_service() -> DocumentationService:
    """Initializes the service with any dependencies it needs."""
    llm_client = get_anyscale_client()
    github_service = get_github_service()
    data_service = get_data_service()
    return DocumentationService(llm_client, github_service, data_service)


# For manually testing this file
if __name__ == "__main__":
    load_dotenv()
    firebase_app = firebase_admin.initialize_app(
        credential=None,
        options={"storageBucket": os.getenv("CLOUD_STORAGE_BUCKET")}
    )
    service = get_documentation_service()

    # Example of running the service once
    # Note: we use asyncio.run because we want to run an async function from
    # a non-async place
    # markdown_doc = asyncio.run(service.generate_doc_for_github_file(
    #     "https://github.com/KTujjar/rocketdocs/blob/main/services/documentation_service.py"
    # ))
    # print(markdown_doc)

    # Example of making concurrent requests
    # Note: we are running a protected method (_run_concurrently) just for demo purposes,
    # this member should only be run internally within DocumentationService.
    files = ["https://github.com/KTujjar/rocketdocs/blob/main/services/documentation_service.py",
             "https://github.com/KTujjar/rocketdocs/blob/main/services/documentation_service.py",
             "https://github.com/KTujjar/rocketdocs/blob/main/services/documentation_service.py"]
    result = asyncio.run(service._run_concurrently(
        [service.generate_doc_for_file(files[0]),
         service.generate_doc_for_file(files[1]),
         service.generate_doc_for_file(files[2])]
    ))
    print(result)
