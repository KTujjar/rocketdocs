from typing import Optional
from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def generate_text(self, prompt: str, system_prompt: str, max_tokens: Optional[int] = None) -> str:
        """Abstract method for generating text."""
        pass
