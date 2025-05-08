from langgraph.prebuilt import create_react_agent
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from shared.db import db as mdb
from langchain.chat_models import init_chat_model
from langgraph.graph.graph import CompiledGraph

from langchain_community.utilities import SQLDatabase
from sql_qa.config import get_config

config = get_config()


def get_agent_executor(db: SQLDatabase) -> CompiledGraph:

    llm = init_chat_model(config.llm.provider, model_provider=config.llm.model_provider)

    # Format the prompt template with configuration values
    system_message = config.prompt.template.format(
        dialect=config.database.dialect, top_k=config.database.top_k
    )

    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    tools = toolkit.get_tools()
    agent_executor = create_react_agent(llm, tools, prompt=system_message)

    return agent_executor
