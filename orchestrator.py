import asyncio
from shared.logger import get_main_logger
from langchain_mcp_adapters.client import MultiServerMCPClient
from colorama import Fore, Style
from sql_qa.llm.adapter import get_adapter_class
from sql_qa.prompt.constant import OrchestratorConstant
from sql_qa.prompt.template import Role
from langgraph.checkpoint.memory import InMemorySaver
from langgraph_swarm import create_handoff_tool, create_swarm
from datetime import datetime
import pytz

logger = get_main_logger(__name__, log_file=f"./logs/{__name__}.log")
from sql_qa.config import get_app_config

app_config = get_app_config()
mcp_servers = app_config.mcp_servers
mcp_servers_dict = {s.server_name: list(s.to_dict().values())[0] for s in mcp_servers}

logger.info(f"MCP servers: {mcp_servers_dict}")


def get_current_time() -> str:
    """Get the current time in Vietnam timezone (Asia/Ho_Chi_Minh).

    Returns:
        str: Current time in format 'YYYY-MM-DD HH:MM:SS TZ'
        Example: '2024-03-21 14:30:45 ICT'
    """
    # Get the current time in UTC
    utc_now = datetime.now(pytz.UTC)
    # Convert to local timezone (you can change this to any timezone)
    local_tz = pytz.timezone("Asia/Ho_Chi_Minh")  # Default to Vietnam timezone
    local_time = utc_now.astimezone(local_tz)
    return local_time.strftime("%Y-%m-%d %H:%M:%S %Z")


def get_current_date() -> str:
    """Get the current date in Vietnam timezone (Asia/Ho_Chi_Minh) with weekday.

    Returns:
        str: Current date in format 'YYYY-MM-DD (Weekday)'
        Example: '2024-03-21 (Thursday)'
    """
    # Get the current date in UTC
    utc_now = datetime.now(pytz.UTC)
    # Convert to local timezone (you can change this to any timezone)
    local_tz = pytz.timezone("Asia/Ho_Chi_Minh")  # Default to Vietnam timezone
    local_time = utc_now.astimezone(local_tz)
    return local_time.strftime("%Y-%m-%d (%A)")


async def main_langchain():
    client = MultiServerMCPClient(mcp_servers_dict)

    base_tools = [get_current_time, get_current_date]
    mcp_tools = await client.get_tools()

    checkpointer = InMemorySaver()
    logger.info(f"Tools: {list(t.name for t in mcp_tools)}")
    for tool in mcp_tools:
        keys_to_remove = [key for key in tool.args_schema.keys() if "$" in key]
        for key in keys_to_remove:
            del tool.args_schema[key]
    # logger.info(f"First tool: {tools[0]}")

    adapter_class = get_adapter_class(app_config.orchestrator.model, original=True)
    orchestrator_executor = adapter_class(
        model=app_config.orchestrator.model,
        tools=[
            *base_tools,
            *mcp_tools,
            create_handoff_tool(
                agent_name="clarifier",
                description="Khi người dùng hỏi, đưa câu hỏi về `clarifier` để làm rõ yêu cầu của người dùng",
            ),
        ],
        checkpointer=checkpointer,
        prompt=OrchestratorConstant.orchestrator_system_prompt.format(),
        name="orchestrator",
    )

    clarifier_executor = adapter_class(
        model=app_config.orchestrator.model,
        tools=[
            *base_tools,
            create_handoff_tool(
                agent_name="orchestrator",
                description="Khi xong nhiệm vụ, chuyển giao cuộc hội thoại cho `orchestrator`",
            ),
        ],
        checkpointer=checkpointer,
        prompt=OrchestratorConstant.clarifier_system_prompt.format(),
        name="clarifier",
    )

    workflow = create_swarm(
        [orchestrator_executor, clarifier_executor],
        default_active_agent="orchestrator",
    )
    app = workflow.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "1"}}
    while (user_message := input(Fore.GREEN + "User: " + Style.RESET_ALL)) not in [
        "exit",
        "quit",
        "q",
    ]:
        logger.info(f"User: {user_message}")
        response = await app.ainvoke(
            {
                "messages": [
                    {
                        "role": Role.USER,
                        "content": OrchestratorConstant.request_prompt.format(
                            user_request=user_message
                        ),
                    }
                ]
            },
            config=config,
        )
        print(
            Fore.YELLOW
            + f"Assistant: {response['messages'][-1].content}"
            + Style.RESET_ALL
        )
        logger.info(f"Assistant: {response['messages'][-1].content}")


main = main_langchain

if __name__ == "__main__":
    asyncio.run(main())
