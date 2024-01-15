import asyncio
from typing import Coroutine, List, Any

from schemas.generated_doc import GeneratedDocResponse
from dotenv import load_dotenv

from services.clients.llm_client import LLMClient
from services.clients.openai_client import get_openai_client
from services.clients.github_client import GitHubClient, get_github_client


class DocumentationService:
    def __init__(self, llm_client: LLMClient, github_client: GitHubClient):
        self.llm_client = llm_client
        self.github_client = github_client
        self.system_prompt_for_file = """
            Your job is to provide very high-level documentation of code provided to you.
    
            You will respond in Markdown format, with the following sections:
            ## Description: (a string less than 100 words)
            ## Insights: ([string, string, string])
            
            Here is the code:
            """

    async def generate_doc_for_github_file(self, file_url: str):
        if not file_url:
            raise ValueError("File url cannot be empty")

        file_content = self.github_client.read_file(file_url)

        llm_response = await self.llm_client.generate_text(
            prompt=file_content,
            system_prompt=self.system_prompt_for_file,
            max_tokens=500
        )

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


def get_documentation_service() -> DocumentationService:
    """Initializes the service with any dependencies it needs."""
    openai_client = get_openai_client()
    github_client = get_github_client()
    return DocumentationService(openai_client, github_client)


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
