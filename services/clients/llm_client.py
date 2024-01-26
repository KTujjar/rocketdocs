from abc import ABC, abstractmethod
from typing import Dict, Any

from openai.types.chat import ChatCompletion


class LLMClient(ABC):
    @abstractmethod
    async def generate_text(
            self,
            model: str,
            prompt: str,
            system_prompt: str,
            max_tokens: int | None = None
    ) -> ChatCompletion:
        """Abstract method for generating text."""
        pass

    @abstractmethod
    async def generate_json(
            self, model: str,
            prompt: str,
            system_prompt: str,
            response_schema: Dict[str, Any],
            max_tokens: int | None = None,
    ) -> ChatCompletion:
        """Abstract method for generating JSON."""
        pass
