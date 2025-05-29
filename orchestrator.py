import asyncio
from langgraph.graph.graph import CompiledGraph
from shared.logger import get_main_logger
from langchain_mcp_adapters.client import MultiServerMCPClient
from colorama import Fore, Style
from shared.tool import get_current_time
from shared.tool import get_current_date
from sql_qa.llm.adapter import get_adapter_class
from sql_qa.prompt.constant import OrchestratorConstant
from sql_qa.prompt.template import Role
from langgraph.checkpoint.memory import InMemorySaver
from langgraph_swarm import create_handoff_tool, create_swarm

logger = get_main_logger(__name__, log_file=f"./logs/{__name__}.log")
from sql_qa.config import get_app_config

app_config = get_app_config()
mcp_servers = app_config.mcp_servers
mcp_servers_dict = {s.server_name: list(s.to_dict().values())[0] for s in mcp_servers}

logger.info(f"MCP servers: {mcp_servers_dict}")


async def get_orchestrator_executor() -> CompiledGraph:
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
                description="Khi làm rõ câu hỏi xong, chuyển giao cuộc hội thoại cho `orchestrator`",
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
    return app


async def main_langchain():
    agent_executor = await get_orchestrator_executor()
    config = {"configurable": {"thread_id": "1"}}
    while (user_message := input(Fore.GREEN + "User: " + Style.RESET_ALL)) not in [
        "exit",
        "quit",
        "q",
    ]:
        logger.info(f"User: {user_message}")
        response = await agent_executor.ainvoke(
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
