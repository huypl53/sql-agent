from abc import ABC, abstractmethod
from typing import Optional

from sql_qa.llm.adapter import BaseAdapter
from sql_qa.prompt.template import PromptTemplate


class LLMBaseGeneration(ABC):
    @abstractmethod
    def invoke(self, prompt: PromptTemplate, schema: str, llm: BaseAdapter) -> str:
        pass


class LLMDirectGeneration(LLMBaseGeneration):
    def invoke(self, prompt: PromptTemplate, schema: str, llm: BaseAdapter) -> str:
        pass
