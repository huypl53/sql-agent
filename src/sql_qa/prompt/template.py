from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, computed_field
from string import Template
from enum import Enum
import json
import re


class Role(str, Enum):
    """Enum for different roles in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """A class to manage messages in a conversation."""

    role: Role
    content: str


class TemplateMetadata(BaseModel):
    """Metadata for a prompt template."""

    version: Optional[str] = Field(default=None, description="Version of the template")
    author: Optional[str] = Field(default=None, description="Author of the template")
    tags: Optional[List[str]] = Field(
        default_factory=list, description="Tags for categorizing the template"
    )


class PromptTemplate(BaseModel):
    """A class to manage prompt templates with variable substitution and AI-specific features."""

    template: str
    role: Role = Role.USER
    metadata: Optional[TemplateMetadata] = Field(
        default_factory=TemplateMetadata, description="Metadata for the template"
    )

    def format(self, **kwargs) -> str:
        """
        Format the template with provided variables.

        Args:
            **kwargs: Variables to substitute in the template

        Returns:
            Formatted prompt string
        """

        # Use string Template for safe substitution
        return self.template.format(**kwargs)

    def to_message(self, **kwargs) -> Message:
        """
        Convert the template to a message format suitable for AI models.

        Args:
            **kwargs: Variables to substitute in the template

        Returns:
            Message object
        """
        return Message(role=self.role, content=self.format(**kwargs))


# Example usage:
if __name__ == "__main__":
    template = PromptTemplate(
        template="You are an AI assistant. The user's name is {name} and their question is: {question}",
        role=Role.SYSTEM,
        metadata=TemplateMetadata(
            version="1.0", author="John Doe", tags=["greeting", "introduction"]
        ),
    )

    # Format with new variables
    result = template.format(name="Alice", question="How does this work?")
    print(result)

    # Convert to message format
    message = template.to_message(name="Alice", question="How does this work?")
    print(message)
    print(message.model_dump())

    print("---")
    # Convert to dictionary using Pydantic's built-in method
    template_dict = template.model_dump()
    print(json.dumps(template_dict, indent=2))
