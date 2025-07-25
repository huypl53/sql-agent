import asyncio
import logging
import click
from typing import List, Literal, Optional, Dict, Union
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.graph import CompiledGraph
from openai.types.chat.chat_completion_message import Annotation
from openai.types.chat.completion_create_params import FunctionCall
from pydantic import BaseModel
import pathlib

import uvicorn

from sql_qa.agent.orchestrator import get_orchestrator_executor
from sql_qa.config import get_app_config
from shared.logger import logger

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai.types.chat import (
    ChatCompletionMessage as OpenAiChatCompletionMessage,
    ChatCompletionMessageToolCall,
)
from openai.types.chat.chat_completion import ChatCompletion, Choice
from sql_qa.utils.invocation import ainvoke_agent


app_config = get_app_config()

logger.info(
    "--------------------------------Starting server--------------------------------"
)
logger.info(app_config)

agent_executor: CompiledGraph


class ChatCompletionMessage(BaseModel):
    content: Optional[str] = None
    """The contents of the message."""

    refusal: Optional[str] = None
    """The refusal message generated by the model."""

    role: Literal["user", "assistant", "system", "human"]
    """The role of the author of this message."""

    annotations: Optional[List[Annotation]] = None
    """
    Annotations for the message, when applicable, as when using the
    [web search tool](https://platform.openai.com/docs/guides/tools-web-search?api-mode=chat).
    """

    function_call: Optional[FunctionCall] = None
    """Deprecated and replaced by `tool_calls`.

    The name and arguments of a function that should be called, as generated by the
    model.
    """

    tool_calls: Optional[List[ChatCompletionMessageToolCall]] = None
    """The tool calls generated by the model, such as function calls."""


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatCompletionMessage]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    logit_bias: Optional[Dict[str, int]] = None


app = FastAPI(title="SQL QA API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@click.group()
def serve():
    pass


@serve.command()
@click.option("--port", type=int, default=5000, help="Port number")
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    help="Host address",
)
@click.option("--reload", is_flag=True, help="Reload server")
@click.option("--workers", default=1, help="Worker num")
def start(host, port, reload, workers):
    # TODO: persistance
    # checkpointer = InMemorySaver()
    checkpointer = None

    async def main() -> None:
        global agent_executor
        agent_executor = await get_orchestrator_executor(checkpointer)
        server_config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level=logging.INFO,
            reload=reload,
            workers=workers,
        )
        server = uvicorn.Server(server_config)
        logger.info(f"Starting server at {host}:{port}")
        await server.serve()

    asyncio.run(main())


@app.post("/v1/chat/completions", response_model=ChatCompletion)
async def chat_completions(request: ChatCompletionRequest):
    try:
        # Extract the last user message
        user_messages = [msg for msg in request.messages if msg.role == "user"]
        if not user_messages:
            raise HTTPException(status_code=400, detail="No user message found")

        last_message = user_messages[-1].content

        # Log user input
        logger.info(f"User: {last_message}")

        # configurable = {"configurable": {"thread_id": "1", "user_id": "1"}}
        # Process agent response
        final_response = None

        response = await ainvoke_agent(
            agent_executor,
            {"messages": request.model_dump()["messages"][-10:]},
            # config=configurable,
        )
        final_response = response["messages"][-1]
        # for step in agent_executor.stream(
        #     # {"messages": [HumanMessage(content=last_message)]},
        #     {"messages": request.model_dump()["messages"][-10:]},
        #     # config=configurable,
        #     stream_mode="values",
        # ):
        #     final_response = step["messages"][-1]
        # logger.info(f"Bot: {final_response}")

        # Log final response
        logger.info(f"Bot: {final_response}")

        # Format response in OpenAI-compatible format
        response = ChatCompletion(
            id="chatcmpl-gsv",
            created=int(pathlib.Path(__file__).stat().st_mtime),
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=OpenAiChatCompletionMessage(
                        role="assistant",
                        content=final_response.content if final_response else "",
                        refusal=None,
                        annotations=[],
                    ),
                    logprobs=None,
                    finish_reason="stop",
                )
            ],
            # usage=Usage(
            #     prompt_tokens=0,
            #     completion_tokens=0,
            #     total_tokens=0,
            #     prompt_tokens_details=TokenDetails(),
            #     completion_tokens_details=CompletionTokenDetails(),
            # ),
            object="chat.completion",
            service_tier="default",
        )

        return response

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    serve()
