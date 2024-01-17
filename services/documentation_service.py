import asyncio
import http.client
from typing import Coroutine, List, Any, Dict
from schemas.documentation_generation import DocsStatusEnum, FirestoreDocumentationCreateModel, \
    FirestoreDocumentationUpdateModel, GeneratedDocResponse, LlmModelEnum
from services.clients.firebase_client import FirebaseClient, get_firebase_client
from google.cloud.firestore_v1 import DocumentReference
from fastapi import BackgroundTasks, HTTPException

from dotenv import load_dotenv

from services.clients.llm_client import LLMClient
from services.clients.openai_client import get_openai_client
from services.clients.github_client import GitHubClient, get_github_client

SYSTEM_PROMPT_FOR_FILES = """
Your job is to provide very high-level documentation of code provided to you.
    
You will respond in Markdown format, with the following sections:
## Description: (a string less than 100 words)
## Insights: ([string, string, string])

Here is the code:
"""


class DocumentationService:
    def __init__(self, llm_client: LLMClient, github_client: GitHubClient, firebase_client: FirebaseClient):
        self.llm_client = llm_client
        self.github_client = github_client
        self.firebase_client = firebase_client
        self.system_prompt_for_file = SYSTEM_PROMPT_FOR_FILES

    async def generate_doc_for_github_file(
            self,
            file_url: str,
            model: LlmModelEnum = LlmModelEnum.MIXTRAL
    ):
        if not file_url:
            raise ValueError("File url cannot be empty")

        file_content = self.github_client.read_file(file_url)

        llm_response = await self.llm_client.generate_text(
            model=model,
            prompt=file_content,
            system_prompt=self.system_prompt_for_file,
            max_tokens=500
        )
        if llm_response[0] == " ":
            llm_response = llm_response[1:]

        response = GeneratedDocResponse(content=llm_response)

        return response

    @staticmethod
    async def _run_concurrently(coroutines: List[Coroutine]) -> tuple[BaseException | Any]:
        """This method leverages the asyncio library to run Coroutines concurrently.
        :returns: an ordered tuple with the results of the coroutines, including exceptions
        """
        tasks = []
        for coroutine in coroutines:
            tasks.append(asyncio.ensure_future(coroutine))
        return await asyncio.gather(*tasks, return_exceptions=True)

    # background tasks for generating the documentation
    def generate_documentation_background(
            self,
            firebase_file_id: str,
            github_url: str,
            model: LlmModelEnum = None
    ):
        generated_docs = asyncio.run(self.generate_doc_for_github_file(github_url, model))

        blob_url = self.firebase_client.get_blob_url(firebase_file_id)

        self.firebase_client.add_blob(blob_url, generated_docs.content)

        self.firebase_client.update_document(
            FirebaseClient.TEST_COLLECTION,
            firebase_file_id,
            FirestoreDocumentationUpdateModel(
                bucket_url=blob_url,
                status=DocsStatusEnum.COMPLETED
            ).model_dump()
        )

    def create_document_generation_job(
            self,
            background_tasks: BackgroundTasks,
            github_url: str,
            model: LlmModelEnum = None
    ) -> DocumentReference:
        document_ref = self.firebase_client.add_document(
            FirebaseClient.TEST_COLLECTION,
            FirestoreDocumentationCreateModel(
                github_url=github_url,
                bucket_url=None,
                status=DocsStatusEnum.STARTED
            ).model_dump()
        )

        # add task to be done async
        background_tasks.add_task(
            self.generate_documentation_background,
            document_ref.id,
            github_url,
            model
        )

        return document_ref

    def get_documentation(self, doc_id: str) -> Dict[str, Any]:
        document_snapshot = self.firebase_client.get_document(
            self.firebase_client.TEST_COLLECTION,
            doc_id
        )

        if not document_snapshot:
            raise HTTPException(status_code=http.client.NOT_FOUND, detail=f"Document {doc_id} not found.")

        # adding id field since Firestore does not do it naturally
        document_dict = document_snapshot.to_dict()
        document_dict["id"] = document_snapshot.id

        return document_dict

    def get_documentation_with_content(self, doc_id: str) -> Dict[str, Any]:
        doc = self.get_documentation(doc_id)

        status = DocsStatusEnum(doc.get("status"))
        blob_url = doc.get("bucket_url")

        # if it is completed get the content, otherwise return None
        doc["content"] = None
        if status == DocsStatusEnum.COMPLETED:
            doc["content"] = self.firebase_client.get_blob(blob_url).download_as_text()

        return doc


def get_documentation_service() -> DocumentationService:
    """Initializes the service with any dependencies it needs."""
    openai_client = get_openai_client()
    github_client = get_github_client()
    firebase_client = get_firebase_client()
    return DocumentationService(openai_client, github_client, firebase_client)


# For manually testing this file
if __name__ == "__main__":
    load_dotenv()
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
