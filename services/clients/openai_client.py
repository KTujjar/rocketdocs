import os

from typing import Optional
from services.clients.llm_client import LLMClient
from openai import OpenAI


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.openai = OpenAI(api_key=self.api_key, base_url=base_url)

    async def generate_text(self, prompt: str, system_prompt: str, max_tokens: Optional[int] = None) -> str:
        completion = self.openai.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens or 200
        )

        return completion.choices[0].message.content
        # return """This is an example response"""


def get_openai_client(model):
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    return OpenAIClient(api_key, base_url, model)
