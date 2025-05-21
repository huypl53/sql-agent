import logging
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
from shared.db import get_db

# from sql_qa.config import DEFAULT_CONFIG
from sql_qa.chat import gen_agent_executor
from sql_qa.config import get_app_config
from sql_qa.schema import (
    AssistantMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    CompletionTokenDetails,
    TokenDetails,
    Usage,
)

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
    config.logging.level,
    log_file=config.logging.log_dir,
    max_bytes=config.logging.max_bytes,
    backup_count=config.logging.backup_count,
)
logger.info(f"Working directory: {os.getcwd()}")

# Initialize LLM and agent
logger.info(f"LLM: {config.llm.provider} ({config.llm.model_provider})")

mdb = get_db()
agent_executor, checkpointer = next(gen_agent_executor(mdb))


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    try:
        # Extract the last user message
        user_messages = [msg for msg in request.messages if msg.role == "user"]
        if not user_messages:
            raise HTTPException(status_code=400, detail="No user message found")

        last_message = user_messages[-1].content

        # Log user input
        logger.info(f"User: {last_message}")

        configurable = {"configurable": {"thread_id": "1", "user_id": "1"}}
        # Process agent response
        final_response = None
        for step in agent_executor.stream(
            # {"messages": [HumanMessage(content=last_message)]},
            {"messages": request.model_dump()["messages"][-10:]},
            config=configurable,
            stream_mode="values",
        ):
            final_response = step["messages"][-1]
            logger.info(f"Bot: {final_response}")

        # Log final response
        logger.info(f"Bot: {final_response}")

        # Format response in OpenAI-compatible format
        response = ChatCompletionResponse(
            id="chatcmpl-gsv",
            created=int(pathlib.Path(__file__).stat().st_mtime),
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=AssistantMessage(
                        role="assistant",
                        content=final_response.content,
                        refusal=None,
                        annotations=[],
                    ),
                    logprobs=None,
                    finish_reason="stop",
                )
            ],
            usage=Usage(
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                prompt_tokens_details=TokenDetails(),
                completion_tokens_details=CompletionTokenDetails(),
            ),
            service_tier="default",
        )

        return response

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def main() -> None:
    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level=config.server.log_level,
        reload=config.server.reload,
        workers=config.server.workers,
    )


if __name__ == "__main__":
    main()
