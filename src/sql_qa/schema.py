from typing import List, Optional, Any
from pydantic import BaseModel


# Pydantic models for request/response
class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False


class TokenDetails(BaseModel):
    cached_tokens: int = 0
    audio_tokens: int = 0


class CompletionTokenDetails(BaseModel):
    reasoning_tokens: int = 0
    audio_tokens: int = 0
    accepted_prediction_tokens: int = 0
    rejected_prediction_tokens: int = 0


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_tokens_details: TokenDetails
    completion_tokens_details: CompletionTokenDetails


class AssistantMessage(BaseModel):
    role: str
    content: str
    refusal: Optional[str] = None
    annotations: List[Any] = []


class Choice(BaseModel):
    index: int
    message: AssistantMessage
    logprobs: Optional[Any] = None
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Usage
    service_tier: str = "default"
