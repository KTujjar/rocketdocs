import simplejson as json
import os
from typing import Dict, List, Type, Union

from openai.types.chat import ChatCompletion
from openai.types import CreateEmbeddingResponse
from pydantic import BaseModel

from schemas.documentation_generation import LlmJsonResponse
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
            temperature: float = 1.0,
            max_tokens: int | None = None
    ) -> ChatCompletion:
        completion = await self.anyscale.chat.completions.create(
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
        completion = await self.anyscale.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        return completion
    
    async def generate_json(
            self,
            model: str,
            prompt: str,
            system_prompt: str,
            response_model: Type[BaseModel],
            temperature: float = 1.0,
            max_retries: int = 1,
            max_tokens: int | None = None,
    ) -> LlmJsonResponse:
        if max_retries != 1:
            raise NotImplementedError("Anyscale retries not supported yet")

        completion = await self.anyscale.chat.completions.create(
            model=model,
            response_format={
              "type": "json_object",
              "schema": response_model.model_json_schema()
            },
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )

        try:
            parsed_json = json.loads(completion.choices[0].message.content)
            content = response_model(**parsed_json)
        except json.JSONDecodeError as e:
            raise ValueError("LLM output not parsable")

        llm_json_response = LlmJsonResponse(
            content=content,
            usage=completion.usage,
            finish_reason=completion.choices[0].finish_reason
        )

        return llm_json_response
    
    async def generate_embedding(
            self, 
            model: str, 
            input: Union[str, List[str], List[int], List[List[int]]]
    ) -> CreateEmbeddingResponse:
        if isinstance(input, list) and len(input) > 2048:
            raise ValueError("Input is too long, maximum batch size is 2048 embeddings")
        embedding = await self.anyscale.embeddings.create(
            model=model,
            input=input
        )
        return embedding
    


def get_anyscale_client():
    api_key = os.getenv("ANYSCALE_API_KEY")
    return AnyscaleClient(api_key)
