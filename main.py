import asyncio
from shared.logger import get_logger
import pathlib
import os
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
import uvicorn

# from shared.db import get_db

# from sql_qa.config import DEFAULT_CONFIG
from orchestrator import CompiledGraph, get_orchestrator_executor
from sql_qa.config import get_app_config
from openai import OpenAI
from openai.types.chat import ChatCompletionMessage
from openai.types.chat.chat_completion import ChatCompletion, Choice

from sql_qa.utils.invocation import ainvoke_agent

load_dotenv()

# Load configuration from YAML file
# Register environment variable resolver
# OmegaConf.register_resolver("env", lambda x: os.environ.get(x, ""))


app = FastAPI(title="SQL QA API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

config = get_app_config()
# Initialize logger
logger = get_logger(
    "main",
    log_file=config.logging.log_dir,
    max_bytes=config.logging.max_bytes,
    backup_count=config.logging.backup_count,
)
logger.info(f"Working directory: {os.getcwd()}")


# mdb = get_db()
# agent_executor, checkpointer = next(gen_agent_executor(mdb))


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


agent_executor: CompiledGraph


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
                    message=ChatCompletionMessage(
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


async def main() -> None:
    global agent_executor
    agent_executor = await get_orchestrator_executor(None)
    server_config = uvicorn.Config(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level=config.server.log_level,
        reload=config.server.reload,
        workers=config.server.workers,
    )
    server = uvicorn.Server(server_config)
    logger.info(f"Starting server at {config.server.host}:{config.server.port}")
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
