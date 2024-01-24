import os
from typing import Dict, Any

from openai.types.chat import ChatCompletion

from services.clients.llm_client import LLMClient
from openai import AsyncOpenAI


class AnyscaleClient(LLMClient):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.endpoints.anyscale.com/v1"
        # Anyscale can use the OpenAI's library to perform operations
        self.anyscale = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def generate_text(
            self, model: str,
            prompt: str,
            system_prompt: str,
            max_tokens: int | None = None
    ) -> ChatCompletion:
        completion = await self.anyscale.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens
        )

        return completion

    async def generate_json(
            self,
            model: str,
            prompt: str,
            system_prompt: str,
            response_schema: Dict[str, Any],
            max_tokens: int | None = None,
    ) -> ChatCompletion:
        completion = await self.anyscale.chat.completions.create(
            model=model,
            response_format={
              "type": "json_object",
              "schema": response_schema
            },
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens
        )

        return completion


def get_anyscale_client():
    api_key = os.getenv("ANYSCALE_API_KEY")
    return AnyscaleClient(api_key)
