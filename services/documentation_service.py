import asyncio
import json
import os
import time
from typing import Coroutine, List, Any, Dict, Type, Optional, Tuple
from collections import deque, defaultdict

import firebase_admin
from github.ContentFile import ContentFile
from openai.types.chat import ChatCompletion
from pydantic import BaseModel

from schemas.documentation_generation import StatusEnum, \
    GeneratedDoc, LlmModelEnum, LlmFileDocSchema, RepoFormatted, \
    ReposResponseModel, FirestoreDoc, FirestoreRepo, FirestoreDocType, LlmFolderDocSchema
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
        self.system_prompt_for_file_json = ("Your job is to generate concise high-level documentation of a file, "
                                            "based on its code. Respond in JSON.")
        self.system_prompt_for_folder_json = ("Your job is to generate concise high-level documentation of a "
                                              "folder, based on the description of its contents. Respond in JSON.")
        self.system_prompt_for_markdown_content = ("Your job is to format received input into concise documentation. "
                                                   "Respond in Markdown text.")

    async def generate_doc_for_file(
            self,
            file: ContentFile,
            model: LlmModelEnum,
    ) -> GeneratedDoc:
        if not file or file.type != FirestoreDocType.FILE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="File cannot be empty")

        user_prompt = f"{file.path}:\n{file.decoded_content}\nRemember to respond in less than 100 words."
        llm_completion = await self._generate_doc_completion(
            model,
            user_prompt,
            self.system_prompt_for_file_json,
            LlmFileDocSchema
        )

        json_content = self._parse_and_validate_llm_completion(llm_completion)

        markdown_content = await self._generate_markdown_content(model, json_content)

        return GeneratedDoc(
            relative_path=file.path,
            usage=llm_completion.usage,
            extracted_data=json_content,
            markdown_content=markdown_content
        )

    async def generate_doc_for_folder(
            self,
            folder: FirestoreDoc,
            files: List[FirestoreDoc],
            model: LlmModelEnum
    ) -> GeneratedDoc:
        self._validate_folder_and_files(folder, files)

        user_prompt = (
            "This is the root folder."
            if not folder.relative_path
            else f"This is the {folder.relative_path} folder."
        )
        user_prompt += f" It contains:\n" + "\n".join(
            f"{file.relative_path}: {file.extracted_data.get('description')}" for file in files
        )
        user_prompt += "\nRemember to respond in less than 100 words."

        llm_completion = await self._generate_doc_completion(
            model,
            user_prompt,
            self.system_prompt_for_folder_json,
            LlmFolderDocSchema
        )
        json_content = self._parse_and_validate_llm_completion(llm_completion)

        markdown_content = await self._generate_markdown_content(model, json_content)

        return GeneratedDoc(
            relative_path=folder.relative_path,
            usage=llm_completion.usage,
            extracted_data=json_content,
            markdown_content=markdown_content
        )

    async def generate_doc(
            self,
            doc_id: str,
            model: LlmModelEnum,
            dependencies: Optional[List[str]] = None
    ):
        if dependencies is None:
            dependencies = []

        print("GENERATING FOR DOC: ", doc_id)
        doc = self.data_service.get_documentation(doc_id)
        dep_docs = [self.data_service.get_documentation(dep) for dep in dependencies]
        self._validate_dependencies(doc, dep_docs)

        self.data_service.update_documentation(doc_id, FirestoreDoc(status=StatusEnum.IN_PROGRESS))

        try:
            if doc.type == FirestoreDocType.FILE:
                file_content = self.github_service.get_file_from_url(doc.github_url)
                generated_doc = await self.generate_doc_for_file(file_content, model)
            elif doc.type == FirestoreDocType.DIRECTORY:
                generated_doc = await self.generate_doc_for_folder(doc, dep_docs, model)
            else:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail="Doc type not supported")
        except Exception as e:
            self.data_service.update_documentation(doc.id, FirestoreDoc(status=StatusEnum.FAILED))
            print("FAILED DOC: ", doc.id)
            raise e

        self.data_service.update_documentation(
            doc_id,
            FirestoreDoc(
                extracted_data=generated_doc.extracted_data,
                markdown_content=generated_doc.markdown_content,
                usage=generated_doc.usage,
                status=StatusEnum.COMPLETED,
            )
        )

        print("FINISHED DOC: ", doc_id)

    def generate_file_doc_background_task(
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
                status=StatusEnum.COMPLETED,
            ).model_dump(exclude_unset=True)
        )

    async def generate_repo_docs_background_task(
            self,
            firestore_repo: FirestoreRepo,
            model: LlmModelEnum
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
            print("-----------------")
            print("starting new round of processing...")
            leaves = [node for node, degree in indegree.items() if degree == 0]
            for leaf in leaves:
                print("PROCESSING LEAF: ", leaf)

            tasks = [
                self.generate_doc(leaf, model, children_graph.get(leaf))
                for leaf in leaves
            ]

            # TODO: implement a retry and error system
            results = await self._run_concurrently(tasks, 30)
            for result in results:
                if isinstance(result, BaseException):
                    raise result

            for leaf in leaves:
                parent = dgraph[leaf]
                if parent:
                    indegree[parent] -= 1
                indegree.pop(leaf)

        self.data_service.update_repo(firestore_repo.id, FirestoreRepo(status=StatusEnum.COMPLETED))
        print(firestore_repo.id)
        print("done my dude")

    def enqueue_generate_file_doc_job(
            self,
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
                status=StatusEnum.IN_PROGRESS
            ).model_dump()
        )

        # add task to be done async
        background_tasks.add_task(
            self.generate_file_doc_background_task,
            doc_id,
            file,
            model
        )

        return doc_id

    def enqueue_generate_repo_docs_job(
            self,
            background_tasks: BackgroundTasks,
            firestore_repo: FirestoreRepo,
            model: LlmModelEnum
    ):
        self.data_service.update_repo(firestore_repo.id, FirestoreRepo(status=StatusEnum.IN_PROGRESS))

        background_tasks.add_task(
            self.generate_repo_docs_background_task,
            firestore_repo,
            model
        )

    def regenerate_doc(
            self,
            background_tasks: BackgroundTasks,
            doc_id: str,
            model: LlmModelEnum
    ) -> str:
        doc = self.data_service.get_documentation(doc_id)

        if doc.status not in [StatusEnum.COMPLETED, StatusEnum.FAILED]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Data is still being generated for this id, so it cannot be regenerated yet.")

        github_file = self.github_service.get_file_from_url(doc.github_url)

        self.data_service.update_documentation(
            doc_id,
            FirestoreDoc(
                github_url=github_file.html_url,
                type=github_file.type,
                size=github_file.size,
                relative_path=github_file.path,
                status=StatusEnum.IN_PROGRESS
            ).model_dump(exclude_unset=True)
        )

        background_tasks.add_task(
            self.generate_file_doc_background_task,
            doc_id,
            github_file,
            model
        )

        return doc_id

    def get_repos(self) -> List[ReposResponseModel]:
        repos_dicts = self.data_service.get_repos()
        repos = [FirestoreRepo(**repo_dict) for repo_dict in repos_dicts]
        repos_formatted = [ReposResponseModel(name=repo.repo_name, id=repo.id, status=self._get_repo_status(repo)) for
                           repo in repos]

        return repos_formatted

    def get_repo(self, repo_id) -> RepoFormatted:
        repo_dict = self.data_service.get_repo(repo_id)
        repo = FirestoreRepo(**repo_dict)
        repo_formatted = self._format_repo(repo)
        return repo_formatted

    async def _generate_doc_completion(
            self,
            model: LlmModelEnum,
            prompt: str,
            system_prompt: str,
            class_type: Type[BaseModel]
    ) -> ChatCompletion:
        return await self.llm_client.generate_json(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            response_schema=class_type.model_json_schema(),
            max_tokens=2048
        )

    async def _generate_markdown_content(self, model: LlmModelEnum, json_content: dict) -> str:
        prompt = json.dumps(json_content)
        prompt += "\n Remember to be concise."

        markdown_llm_completion = await self.llm_client.generate_text(
            model=model,
            prompt=prompt,
            system_prompt=self.system_prompt_for_markdown_content,
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
            print("NON-PARSABLE STRING START\n", json_string, "\nNON-PARSABLE STRING END\n")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="LLM output not parsable")

    @staticmethod
    def _format_repo(repo_response: FirestoreRepo) -> RepoFormatted:
        root_doc: str = repo_response.root_doc
        repo_name: str = repo_response.repo_name
        repo_id: str = repo_response.id
        dependencies: dict[str, str] = repo_response.dependencies
        docs: list[FirestoreDoc] = list(repo_response.docs.values())

        repo_formatted = RepoFormatted(name=repo_name, id=repo_id, tree=[], nodes_map={})

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
    def _get_repo_status(repo_response: FirestoreRepo) -> list[dict[str, StatusEnum]]:
        docs = repo_response.docs

        repo_status = [{doc.id: doc.status} for doc in docs]
        return repo_status

    @staticmethod
    def _validate_folder_and_files(folder: FirestoreDoc, files: List[FirestoreDoc]) -> None:
        if not folder or folder.type != FirestoreDocType.DIRECTORY:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Folder cannot be empty")
        for file in files:
            if file.status != StatusEnum.COMPLETED:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="Files are still being generated")

    @staticmethod
    def _validate_dependencies(parent: FirestoreDoc, dependencies: List[FirestoreDoc]) -> None:
        if parent.type == FirestoreDocType.DIRECTORY and not dependencies:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Dependencies cannot be empty")
        for dep in dependencies:
            if dep.status != StatusEnum.COMPLETED:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="Dependencies are not completed yet.")

    @staticmethod
    def _validate_repo(repo: FirestoreRepo) -> None:
        if not repo.dependencies or not repo.root_doc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Repo does not have a root or dependencies.")

        if repo.status == StatusEnum.IN_PROGRESS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Repo is already in progress.")

    @staticmethod
    async def _run_concurrently(
            coroutines: List[Coroutine],
            batch_size: Optional[int] = None
    ) -> tuple[BaseException | Any]:
        """This method leverages the asyncio library to run Coroutines concurrently.
        :returns: an ordered tuple with the results of the coroutines, including exceptions
        """
        if batch_size:
            results = []
            for i in range(0, len(coroutines), batch_size):
                batch = coroutines[i:i + batch_size]
                results.extend(await asyncio.gather(*batch, return_exceptions=True))
            return tuple(results)
        else:
            return await asyncio.gather(*coroutines, return_exceptions=True)


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
    # test_files = ["https://github.com/KTujjar/rocketdocs/blob/main/services/documentation_service.py",
    #          "https://github.com/KTujjar/rocketdocs/blob/main/services/documentation_service.py",
    #          "https://github.com/KTujjar/rocketdocs/blob/main/services/documentation_service.py"]
    # result = asyncio.run(service._run_concurrently(
    #     [service.generate_doc_for_file(test_files[0]),
    #      service.generate_doc_for_file(test_files[1]),
    #      service.generate_doc_for_file(test_files[2])]
    # ))
    # print(result)

    # Example of generating doc for Folder
    test_task_group = [service.generate_doc_for_folder(
        folder=FirestoreDoc(
            type=FirestoreDocType.DIRECTORY,
            relative_path="clients",
        ),
        files=[
            FirestoreDoc(
                type=FirestoreDocType.FILE,
                status=StatusEnum.COMPLETED,
                relative_path="clients/anyscale_client.py",
                extracted_data={"description": "This file implements an Anyscale client which is a subclass of the "
                                               "LLMClient class. AnyscaleClient is used to interact with the Anyscale "
                                               "service using its API. It provides methods to generate text and JSON "
                                               "responses using specified models and prompts. The client uses the "
                                               "OpenAI's library to perform operations. The get_anyscale_client "
                                               "function is used to get an instance of the AnyscaleClient by "
                                               "retrieving the API key from the environment variable ANYSCALE_API_KEY"}
            ),
            FirestoreDoc(
                type=FirestoreDocType.FILE,
                status=StatusEnum.COMPLETED,
                relative_path="clients/openai_client.py",
                extracted_data={"description": "This module contains the OpenAIClient class which is a specific "
                                               "implementation of the LLMClient abstract class for interacting with "
                                               "OpenAI's API. It provides methods to generate text and JSON responses "
                                               "using OpenAI's models and handles authentication with the API using "
                                               "an API key.The module also includes a get_openai_client() function "
                                               "which returns an instance of the OpenAIClient class initialized with "
                                               "the OPENAI_API_KEY environment variable."}
            ),
            FirestoreDoc(
                type=FirestoreDocType.FILE,
                status=StatusEnum.COMPLETED,
                relative_path="clients/llm_client.py",
                extracted_data={"description": "The `LLMClient` abstract base class (ABC) defines the interface for a "
                                               "client that can communicate with a large language model (LLM) and "
                                               "generate text or JSON responses. It includes two abstract methods: "
                                               "`generate_text` and `generate_json`."}
            )
        ],
        model=LlmModelEnum.MIXTRAL
    )]
    test_doc = asyncio.run(service._run_concurrently(test_task_group, 1))
    print(test_doc)
