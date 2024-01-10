from schemas.generated_doc import GeneratedDocResponse
from dotenv import load_dotenv

from services.llm_client import LLMClient
from services.openai_client import get_openai_client
from services.github_client import GitHubClient, get_github_client


class DocumentationService:
    def __init__(self, llm_client: LLMClient, github_client: GitHubClient):
        self.llm_client = llm_client
        self.github_client = github_client
        self.system_prompt_for_file = """
            Your job is to provide very high-level documentation of code provided to you.
    
            You will respond in Markdown format, with the following sections:
            ## Description: (a string less than 100 words)
            ## Insights: ([string, string, ...] less than 3 strings)
            
            Here is the code:
            """

    def generate_doc_for_github_file(self, file_url: str):
        if not file_url:
            raise ValueError("File url cannot be empty")

        file_content = self.github_client.read_file(file_url)

        llm_response = self.llm_client.generate_text(
            prompt=file_content,
            system_prompt=self.system_prompt_for_file,
            max_tokens=500
        )

        response = GeneratedDocResponse(content=llm_response)

        return response


def get_documentation_service() -> DocumentationService:
    """Initializes the service with any dependencies it needs."""
    openai_client = get_openai_client()
    github_client = get_github_client()
    return DocumentationService(openai_client, github_client)


# For manually testing this file
if __name__ == "__main__":
    load_dotenv()
    service = get_documentation_service()
    markdown_doc = service.generate_doc_for_github_file(
        "https://github.com/carlos-jmh/miniDiscord/blob/main/chat/storage.go"
    )
    print(markdown_doc)
