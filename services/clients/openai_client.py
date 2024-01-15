import os

from typing import Optional
from services.clients.llm_client import LLMClient
from openai import OpenAI


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model="gpt-3.5-turbo"):
        self.api_key = api_key
        self.model = model
        self.openai = OpenAI(api_key=self.api_key)

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


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    return OpenAIClient(api_key)
