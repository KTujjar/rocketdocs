import os
from typing import Dict, Any

from openai.types.chat import ChatCompletion

from services.clients.llm_client import LLMClient
from openai import AsyncOpenAI


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1"
        self.openai = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def generate_text(
            self,
            model: str,
            prompt: str,
            system_prompt: str,
            max_tokens: int | None = 500
    ) -> ChatCompletion:
        completion = await self.openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens
        )
        return completion

    async def generate_json(
            self, model: str,
            prompt: str,
            system_prompt: str,
            response_schema: Dict[str, Any],
            max_tokens: int | None = 500,
    ) -> ChatCompletion:
        raise NotImplementedError


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    return OpenAIClient(api_key)
