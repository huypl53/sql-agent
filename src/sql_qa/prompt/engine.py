from typing import List
from sql_qa.prompt.template import PromptTemplate


class PromptEngine:
    """
    A class to manage prompt templates with variable substitution and AI-specific features.
    """

    def __init__(self, prompt_templates: List[PromptTemplate]):
        self.prompt_templates = prompt_templates

    def get_prompt(self, template_name: str, **kwargs) -> str:
        return self.prompt_templates[template_name].format(**kwargs)
