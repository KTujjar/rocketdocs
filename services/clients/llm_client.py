from abc import ABC, abstractmethod
from typing import Dict, Any, Type

from openai.types.chat import ChatCompletion
from pydantic import BaseModel

from schemas.documentation_generation import LlmJsonResponse


class LLMClient(ABC):
    @abstractmethod
    async def generate_text(
            self,
            model: str,
            prompt: str,
            system_prompt: str,
            temperature: float = 1.0,
            max_tokens: int | None = None
    ) -> ChatCompletion:
        """Abstract method for generating text."""
        pass

    @abstractmethod
    async def generate_json(
            self, model: str,
            prompt: str,
            system_prompt: str,
            response_model: Type[BaseModel],
            temperature: float = 1.0,
            max_retries: int = 1,
            max_tokens: int | None = None,
    ) -> LlmJsonResponse:
        """Abstract method for generating JSON."""
        pass
