import asyncio
import json
import os
from typing import Coroutine, List, Any, Dict
from collections import deque

import firebase_admin
from openai.types.chat import ChatCompletion

from schemas.documentation_generation import DocsStatusEnum, FirestoreDocumentationCreateModel, \
    FirestoreDocumentationUpdateModel, FirestoreRepoCreateModel, RepoResponseModel, LlmModelEnum, GeneratedDoc, LlmModelEnum, LlmProvider, \
    LlmDocSchema, BlobDoc, GitHubFile, RepoFormatted, RepoNode, FirestoreRepoDocModel
from services.clients.anyscale_client import get_anyscale_client
from services.clients.firebase_client import FirebaseClient, get_firebase_client
from fastapi import BackgroundTasks, HTTPException, status

from dotenv import load_dotenv

from services.clients.llm_client import LLMClient
from services.clients.openai_client import get_openai_client
from services.clients.github_client import GitHubClient, get_github_client

SYSTEM_PROMPT_FOR_FILES = "Your job is to provide very high-level documentation of code provided to you. " + \
                          "You will respond in Markdown format, with the following sections:" + \
                          "\n## Description: (a string less than 100 words)" + \
                          "\n## Insights: ([string, string, string])"

SYSTEM_PROMPT_FOR_FILES_JSON = "You are a helpful assistant that summarizes a code's purpose at a high level. " + \
                               "You will respond in JSON format, with strings formatted in Markdown."


class DocumentationService:
    def __init__(self, llm_client: LLMClient, github_client: GitHubClient, firebase_client: FirebaseClient):
        self.llm_client = llm_client
        self.github_client = github_client
        self.firebase_client = firebase_client
        self.system_prompt_for_file = SYSTEM_PROMPT_FOR_FILES
        self.system_prompt_for_file_json = SYSTEM_PROMPT_FOR_FILES_JSON

    async def generate_doc_for_github_file(
            self,
            github_file: GitHubFile,
            model: LlmModelEnum
    ) -> GeneratedDoc:
        if not github_file:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="File cannot be empty")

        user_prompt = f"{github_file.path}:\n" + github_file.content

        llm_completion: ChatCompletion = await self.llm_client.generate_json(
            model=model,
            prompt=user_prompt,
            system_prompt=self.system_prompt_for_file_json,
            response_schema=LlmDocSchema.model_json_schema(),
            max_tokens=2048
        )

        raw_content = llm_completion.choices[0].message.content
        usage = llm_completion.usage
        json_content = self._validate_json(raw_content)
        if not json_content:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="LLM output not parsable")

        response = GeneratedDoc(
            relative_path=github_file.path,
            raw_content=raw_content,
            usage=usage,
            description=json_content["description"],
            insights=json_content["insights"]
        )

        return response

    # background tasks for generating the documentation
    def generate_doc_background_task(
            self,
            firebase_file_id: str,
            github_file: GitHubFile,
            model: LlmModelEnum
    ) -> None:
        generated_doc = asyncio.run(self.generate_doc_for_github_file(github_file, model))

        blob_doc = BlobDoc(**generated_doc.model_dump())
        blob_url = self.firebase_client.get_blob_url(firebase_file_id)
        self.firebase_client.add_blob(blob_url, json.dumps(blob_doc.model_dump()))

        self.firebase_client.update_documentation(
            firebase_file_id,
            FirestoreDocumentationUpdateModel(
                bucket_url=blob_url,
                status=DocsStatusEnum.COMPLETED,
                relative_path=generated_doc.relative_path,
                usage=generated_doc.usage
            ).model_dump()
        )

    def enqueue_generate_doc_job(
            self,
            background_tasks: BackgroundTasks,
            github_url: str,
            model: LlmModelEnum
    ) -> str:
        github_file: GitHubFile = self.github_client.read_file(github_url)

        doc_id = self.firebase_client.add_documentation(
            FirestoreDocumentationCreateModel(
                github_url=github_url,
                bucket_url=None,
                relative_path=github_file.path,
                status=DocsStatusEnum.STARTED
            ).model_dump()
        )

        # add task to be done async
        background_tasks.add_task(
            self.generate_doc_background_task,
            doc_id,
            github_file,
            model
        )

        return doc_id

    def regenerate_doc(
            self,
            background_tasks: BackgroundTasks,
            doc_id: str,
            model: LlmModelEnum
    ) -> str:
        doc = self.firebase_client.get_documentation(doc_id)
        github_url = doc.get("github_url")
        blob_url = doc.get("bucket_url")
        usage = doc.get("usage")
        relative_path = doc.get("relative_path")

        doc_status = DocsStatusEnum(doc.get("status"))

        if doc_status == DocsStatusEnum.STARTED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Data is still being generated for this id, so it cannot be regenerated yet.")

        github_file = self.github_client.read_file(github_url)

        # reset the bucket and set to started
        self.firebase_client.update_documentation(
            doc_id,
            FirestoreDocumentationUpdateModel(
                bucket_url=None,
                status=DocsStatusEnum.STARTED,
                usage=usage,
                relative_path=relative_path
            ).model_dump()
        )

        # delete the blob since we are going to generate and add a new one
        self.firebase_client.delete_blob(blob_url)

        # add task to be done async
        background_tasks.add_task(
            self.generate_doc_background_task,
            doc_id,
            github_file,
            model
        )

        return doc_id

    def get_doc_with_content(self, doc_id: str) -> Dict[str, Any]:
        doc = self.firebase_client.get_documentation(doc_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Documentation {doc_id} not found")

        doc_status = DocsStatusEnum(doc.get("status"))
        blob_url = doc.get("bucket_url")

        # if it is completed get the content, otherwise return None
        doc["content"] = None
        if doc_status == DocsStatusEnum.COMPLETED:
            blob_doc_raw = json.loads(self.firebase_client.get_blob(blob_url).download_as_text())
            blob_doc = BlobDoc(**blob_doc_raw)
            doc["content"] = blob_doc

        return doc

    def delete_doc(self, doc_id):
        # get blob url to delete
        doc = self.firebase_client.get_documentation(doc_id)
        doc_status = DocsStatusEnum(doc.get("status"))

        if doc_status == DocsStatusEnum.STARTED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Data is still being generated for this id, so it cannot be deleted yet.")

        blob_url = doc.get("bucket_url")

        # delete blob first
        self.firebase_client.delete_blob(blob_url)

        # delete firestore entry
        self.firebase_client.delete_documentation(doc_id)

    def get_repos(self) -> list[RepoResponseModel]:
        repos_dicts = self.firebase_client.get_repos()
        models = [RepoResponseModel.model_validate(repo_dict) for repo_dict in repos_dicts]
        return models
    
    def get_repo(self, repo_id) -> RepoResponseModel:
        repo_dict = self.firebase_client.get_repo(repo_id)
        model = RepoResponseModel.model_validate(repo_dict)

        self._format_repo(model)
        return model
    
    @staticmethod
    def _format_repo(repo_response: RepoResponseModel) -> RepoFormatted:
        root_doc: FirestoreRepoDocModel = repo_response.root_doc
        repo_name = repo_response.repo_name
        dependencies: dict[str, str] = repo_response.dependencies
        docs = repo_response.docs

        repo_formatted = RepoFormatted(repo_name=repo_name, tree=[], nodes_map={})

        def find_doc_by_id(docs: list[FirestoreRepoDocModel], id) -> FirestoreRepoDocModel:
            for doc in docs:
                if doc.id == id:
                    return doc
            return None

        def process_node(parent_id, child_id):
            parent_data: FirestoreRepoDocModel = find_doc_by_id(docs, parent_id) 
            child_data: FirestoreRepoDocModel = find_doc_by_id(docs, child_id) 

            repo_formatted.insert_node(parent_data, child_data)
       
        used = set()
        def bfs(root):
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


        bfs(root_doc.id)
        print(repo_formatted)




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
    github_client = get_github_client()
    firebase_client = get_firebase_client()
    return DocumentationService(llm_client, github_client, firebase_client)


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
        [service.generate_doc_for_github_file(files[0]),
         service.generate_doc_for_github_file(files[1]),
         service.generate_doc_for_github_file(files[2])]
    ))
    print(result)
