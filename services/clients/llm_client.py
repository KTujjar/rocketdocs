from typing import Optional
from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: str, max_tokens: int | None = None) -> str:
        """Abstract method for generating text."""
        pass
