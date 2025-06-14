import asyncio
from typing import (
    Any,
    Callable,
    Coroutine,
    List,
    Union,
    cast,
)
from langchain_core.messages import AnyMessage
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.graph.graph import CompiledGraph
from langgraph.prebuilt import create_react_agent
from shared.logger import get_main_logger
from langchain_mcp_adapters.client import MultiServerMCPClient
from colorama import Fore, Style
from shared.tool import get_current_time
from shared.tool import get_current_date
from sql_qa.llm.adapter import get_react_agent, get_chat_model_init
from sql_qa.prompt.constant import OrchestratorConstant, UserQuestionEnhancementConstant
from sql_qa.prompt.template import Role
from langgraph.checkpoint.memory import InMemorySaver
from langgraph_swarm import create_handoff_tool, create_swarm
from langgraph.graph import END, START, StateGraph
from langgraph_supervisor import create_supervisor, supervisor
from sql_qa.schema.graph import EnhancementState
from sql_qa.schema.tool import Text2SqlResult

logger = get_main_logger(__name__, log_file=f"./logs/{__name__}.log")

from sql_qa.config import get_app_config

app_config = get_app_config()
mcp_servers = app_config.mcp_servers
mcp_servers_dict = {s.server_name: list(s.to_dict().values())[0] for s in mcp_servers}

logger.info(f"MCP servers: {mcp_servers_dict}")


mcp_client = MultiServerMCPClient(
    {
        "mcp-server-text2sql": {
            "command": "uv",
            # Make sure to update to the full absolute path to your math_server.py file
            "args": [
                "run",
                "text2sql.py",
                "mcp-server",
                "--transport",
                "stdio",
                "--mock",
            ],
            "transport": "stdio",
        }
    }
)


async def get_orchestrator_executor_v1() -> CompiledGraph:
    base_tools = [get_current_time, get_current_date]
    mcp_tools = await mcp_client.get_tools()

    checkpointer = InMemorySaver()
    logger.info(f"Tools: {list(t.name for t in mcp_tools)}")
    for tool in mcp_tools:
        keys_to_remove = [key for key in tool.args_schema.keys() if "$" in key]
        for key in keys_to_remove:
            del tool.args_schema[key]
    # logger.info(f"First tool: {tools[0]}")

    orchestrator_executor = get_react_agent(
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

    clarifier_executor = get_react_agent(
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
                        # "content": OrchestratorConstant.request_prompt.format(
                        #     user_request=user_message
                        # ),
                        "content": user_message,
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


class EnhancementGraphBuilder:
    """Enhance user prompt with tools and execute them.

    Flow:
    1. Execute tools on user question concurrently.
    2. Merge results from all tools.
    3. Return the final state after tool execution.

    """

    def __init__(
        self,
        checkpointer=None,
        *,
        tools: (
            List[
                Union[
                    Callable[[EnhancementState], Coroutine[None, None, Any]],
                    Callable[[EnhancementState], Any],
                ]
            ]
            | None
        ) = None,
    ):
        self.checkpointer = checkpointer
        self.summary_agent = None
        self._tools = tools or []
        self._graph: CompiledGraph

        self._init()

    def _init(self):
        self._build_graph()
        self._summerizer = get_chat_model_init(app_config.orchestrator.model)

    def _build_graph(self):
        graph = StateGraph(EnhancementState)
        self._graph = (
            graph.add_node("tool_execution", self._execute_tools)
            .add_node("merge_results", self.merge_results)
            .add_edge(START, "tool_execution")
            .add_edge("tool_execution", "merge_results")
            .add_edge("merge_results", END)
            .compile(name="enhancement_agent", checkpointer=self.checkpointer)
        )

        # return self.graph

    @property
    def graph(self) -> CompiledGraph:
        if not hasattr(self, "_graph"):
            self._build_graph()
        return self._graph

    async def _execute_tools(self, state: EnhancementState) -> EnhancementState:
        tasks = []
        logger.info(f"State: {state}")
        for tool in self._tools:
            if hasattr(tool, "__call__"):
                if asyncio.iscoroutinefunction(tool):
                    tasks.append(tool(state))
                else:
                    tasks.append(asyncio.to_thread(tool, state))
        # Run all tools concurrently and get their results
        results = await asyncio.gather(*tasks)
        logger.info(f"Tool results: {results}")
        logger.info(f"State: {state}")
        return cast(
            EnhancementState,
            {
                "tool_results": results,
                "user_question": state["messages"][-1]["content"],
            },
        )

    async def merge_results(self, state: EnhancementState) -> EnhancementState:
        # Merge all tool results into a single string
        merged_results = "- " + "\n- ".join(state["tool_results"])
        user_question = state["user_question"]
        summarized_result = await self._summerizer.ainvoke(
            UserQuestionEnhancementConstant.summary_prompt.format(
                evidence=merged_results,
                user_question=user_question or "<không có câu hỏi>",
            ),
        )
        return {"messages": [summarized_result]}

    async def get_executor(self) -> CompiledGraph:
        return await get_orchestrator_executor_v1()


async def get_orchestrator_executor(checkpointer=None) -> CompiledGraph:
    # Create supervisor workflow
    from sql_qa.llm.tool import (
        llm_clarify_date_time_tool,
        llm_intent_clarify_tool,
    )

    enhancement_agent = EnhancementGraphBuilder(
        tools=[llm_clarify_date_time_tool, llm_intent_clarify_tool]
    ).graph

    async with mcp_client.session("mcp-server-text2sql") as session:
        mcp_tools = await load_mcp_tools(session)

    logger.info(f"MCP tools: {mcp_tools}")
    sql_generation_agent = create_react_agent(
        name="sql_generation_agent",
        model=app_config.orchestrator.model,
        tools=mcp_tools,
        checkpointer=checkpointer,
        prompt="""
- Bạn là chuyên gia sử dụng công cụ để thực hiện tác vụ truy vấn dữ liệu. Nhiệm vụ của bạn là sử dụng sử dụng công cụ để trả lời câu hỏi của người dùng
- Bạn chỉ được sử dụng công cụ để trả lời câu hỏi của người dùng
- Tuyệt đối không sử dụng dữ liệu tri thức vốn có của bạn để trả lời.
        """,
        # prompt=OrchestratorConstant.sql_generation_system_prompt.format(),
        # state_schema=Text2SqlResult,
    )

    model = get_chat_model_init(app_config.orchestrator.model)
    workflow = create_supervisor(
        [enhancement_agent, sql_generation_agent],
        model=model,
        prompt=OrchestratorConstant.supervisor_system_prompt.format(),
        output_mode="last_message",
        # state_schema=None,
    )

    # Compile and run
    app = workflow.compile()
    return app
    pass


main = main_langchain

if __name__ == "__main__":
    asyncio.run(main())
