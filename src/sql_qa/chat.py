from langgraph.prebuilt import create_react_agent
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langgraph.checkpoint.postgres import PostgresSaver
from langchain.chat_models import init_chat_model
from langgraph.graph.graph import CompiledGraph
from typing import Generator, Tuple
from langgraph.checkpoint.memory import MemorySaver
from langchain_community.utilities import SQLDatabase
from sql_qa.config import get_app_config
from shared.logger import get_logger

config = get_app_config()
logger = get_logger(__name__)

# Global checkpointer instance
checkpointer = MemorySaver()


def gen_agent_executor(
    db: SQLDatabase,
) -> Generator[Tuple[CompiledGraph, PostgresSaver], None, None]:

    # with PostgresSaver.from_conn_string(config.persist.host) as cp:
    llm = init_chat_model(config.llm.provider, model_provider=config.llm.model_provider)

    # Format the prompt template with configuration values
    system_message = config.prompt.template.format(
        dialect=config.database.dialect, top_k=config.database.top_k
    )
    logger.info(f"System message: {system_message}")

    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    tools = toolkit.get_tools()
    logger.info(f"Tools: {tools}")

    agent_executor = create_react_agent(
        llm, tools, prompt=system_message, checkpointer=checkpointer
    )

    while True:
        yield agent_executor, checkpointer
