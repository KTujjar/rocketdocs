import json
import os
from typing import Dict, List, Type

import instructor
from openai.types.chat import ChatCompletion
from pydantic import BaseModel

from schemas.documentation_generation import LlmJsonResponse
from services.clients.llm_client import LLMClient
from openai import AsyncOpenAI


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1"
        self.openai = instructor.patch(AsyncOpenAI(api_key=self.api_key, base_url=self.base_url))

    async def generate_text(
            self,
            model: str,
            prompt: str,
            system_prompt: str,
            temperature: float = 1.0,
            max_tokens: int | None = 500
    ) -> ChatCompletion:
        completion = await self.openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        return completion
    
    async def generate_messages(
            self, 
            model: str,
            messages: List[Dict[str, str]],
            temperature: float = 1.0,
            max_tokens: int | None = None
    ) -> ChatCompletion:
        completion = await self.openai.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        return completion

    # noinspection PyArgumentList
    async def generate_json(
            self,
            model: str,
            prompt: str,
            system_prompt: str,
            response_model: Type[BaseModel],
            temperature: float = 1.0,
            max_retries: int = 1,
            max_tokens: int | None = 500,
    ) -> LlmJsonResponse:
        completion_content = await self.openai.chat.completions.create(
            model=model,
            response_model=response_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_retries=max_retries,
            max_tokens=max_tokens
        )

        raw_response_json = completion_content._raw_response.model_dump_json(indent=2)
        response_dict = json.loads(raw_response_json)
        completion = ChatCompletion(**response_dict)

        llm_json_response = LlmJsonResponse(
            content=completion_content,
            usage=completion.usage,
            finish_reason=completion.choices[0].finish_reason,
        )

        return llm_json_response


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    return OpenAIClient(api_key)
