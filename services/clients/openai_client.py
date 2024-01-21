import os

from services.clients.llm_client import LLMClient
from openai import AsyncOpenAI


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.openai = AsyncOpenAI(api_key=self.api_key, base_url=base_url)

    async def generate_text(self, model: str, prompt: str, system_prompt: str, max_tokens: int | None = None) -> str:
        completion = await self.openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens
        )

        return completion.choices[0].message.content


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    return OpenAIClient(api_key, base_url)
