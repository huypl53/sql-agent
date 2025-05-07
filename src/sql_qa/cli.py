import logging
from shared import db as mdb
from shared.logger import get_logger
import pathlib
import os
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
from omegaconf import OmegaConf

load_dotenv()

# Load configuration from YAML file
CONFIG_PATH = pathlib.Path(__file__).parent / "config.yaml"
DEFAULT_CONFIG = OmegaConf.load(CONFIG_PATH)
# Register environment variable resolver
# OmegaConf.register_resolver("env", lambda x: os.environ.get(x, ""))


# Pydantic models for request/response
class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]


app = FastAPI(title="SQL QA API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize logger
logger = get_logger(
    "main",
    logging.INFO,
    log_file=DEFAULT_CONFIG.logging.log_dir,
    max_bytes=DEFAULT_CONFIG.logging.max_bytes,
    backup_count=DEFAULT_CONFIG.logging.backup_count,
)
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Configuration: {OmegaConf.to_yaml( DEFAULT_CONFIG )}")

# Initialize LLM and agent
logger.info(f"LLM: {DEFAULT_CONFIG.llm.provider} ({DEFAULT_CONFIG.llm.model_provider})")
llm = init_chat_model(
    DEFAULT_CONFIG.llm.provider, model_provider=DEFAULT_CONFIG.llm.model_provider
)

db = mdb.db
toolkit = SQLDatabaseToolkit(db=db, llm=llm)
tools = toolkit.get_tools()

# Format the prompt template with configuration values
system_message = DEFAULT_CONFIG.prompt.template.format(
    dialect=DEFAULT_CONFIG.database.dialect, top_k=DEFAULT_CONFIG.database.top_k
)
agent_executor = create_react_agent(llm, tools, prompt=system_message)


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

        # Process agent response
        final_response = None
        for step in agent_executor.stream(
            {"messages": [HumanMessage(content=last_message)]},
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
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": final_response.content,
                    },
                    "finish_reason": "stop",
                }
            ],
            usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        )

        return response

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def main() -> None:
    uvicorn.run(
        app,
        host=DEFAULT_CONFIG.server.host,
        port=DEFAULT_CONFIG.server.port,
        log_level=DEFAULT_CONFIG.server.log_level,
        reload=DEFAULT_CONFIG.server.reload,
        workers=DEFAULT_CONFIG.server.workers,
    )


if __name__ == "__main__":
    main()
