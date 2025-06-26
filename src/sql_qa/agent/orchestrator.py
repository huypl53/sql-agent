import asyncio
from typing import (
    Annotated,
    Any,
    Callable,
    Coroutine,
    List,
    TypedDict,
    Union,
    cast,
)


from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, RemoveMessage
from langchain_core.tools import tool
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.graph.graph import CompiledGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.prebuilt import create_react_agent
from shared.logger import logger
from langchain_mcp_adapters.client import MultiServerMCPClient
from colorama import Fore, Style
from shared.tool import get_current_time
from shared.tool import get_current_date
from sql_qa.agent import domain
from sql_qa.agent.domain import (
    QuestionDomainAgent,
    QuestionDomainAgentState,
    TQuestionDomain,
    get_domain_knowledge,
)
from sql_qa.llm.adapter import get_react_agent
from sql_qa.prompt.constant import DomainConstant
from sql_qa.prompt.template import Role
from langgraph.checkpoint.memory import InMemorySaver
from langgraph_swarm import SwarmState, create_handoff_tool, create_swarm
from langgraph.graph import END, START, StateGraph


from sql_qa.config import get_app_config

app_config = get_app_config()
mcp_servers = app_config.mcp_servers
mcp_servers_dict = {s.server_name: s for s in mcp_servers}

logger.info(f"MCP servers: {mcp_servers_dict}")


class OrchestratorState(QuestionDomainAgentState, SwarmState):
    # messages: Annotated[List[AnyMessage], operator.add]
    pass


class OrchestratorGraph:

    def __init__(self) -> None:
        self.graph = self._build_graph()

    def _build_graph(self):
        graph_builder = StateGraph(OrchestratorState)

        return graph_builder.compile()

    # {
    #     "mcp-server-text2sql": {
    #         "command": "uv",
    #         # Make sure to update to the full absolute path to your math_server.py file
    #         "args": [
    #             "run",
    #             "text2sql.py",
    #             "mcp-server",
    #             "--transport",
    #             "stdio",
    #             "--mock",
    #         ],
    #         "transport": "stdio",
    #     }
    # }


mcp_client = MultiServerMCPClient(mcp_servers_dict)


async def main_langchain():
    checkpointer = InMemorySaver()
    agent_executor = await get_orchestrator_executor(checkpointer)
    # config = {"configurable": {"thread_id": "1"}}
    user_id = "uid_01"
    config = {"configurable": {"thread_id": "1", "user_id": user_id}}
    while (user_message := input(Fore.GREEN + "User: " + Style.RESET_ALL)) not in [
        "exit",
        "quit",
        "q",
    ]:
        logger.info(f"User: {user_message}")
        response = await agent_executor.ainvoke(
            {
                "messages": [
                    {"role": Role.USER, "content": user_message},
                ],
                "domain": "accountant",
            },
            config,
        )
        print(
            Fore.YELLOW
            + f"Assistant: {response['messages'][-1].content}"
            + Style.RESET_ALL
        )
        logger.info(f"Assistant: {response['messages'][-1].content}")


def domain_post_hook(state: OrchestratorState) -> OrchestratorState:
    update: OrchestratorState = {}
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:

        return update
    last_ai_message: AIMessage | None = None
    if len(state["messages"]) < 2:
        return update
    for msg in state["messages"][-2::-1]:
        if isinstance(msg, AIMessage):
            last_ai_message = msg
            break

    if not last_ai_message:
        logger.warning("No AI message containing user question found!")
        return update

    summary_model = init_chat_model(app_config.question_proc.model)
    summarizer_resp = summary_model.invoke(
        [
            *state["messages"][:-1],
            HumanMessage(
                content="Dựa trên lịch sử cuộc trò chuyện, tổng hợp lại thành câu hỏi trên vai của tôi để hỏi AI. Lưu ý chỉ trả về câu hỏi, không giải thích hay chú thích gì thêm."
            ),
        ]
    )
    update.update(
        {
            "messages": [
                # RemoveMessage(id=last_ai_message.id),
                RemoveMessage(REMOVE_ALL_MESSAGES),
                # HumanMessage(enhanced_user_questions),
                HumanMessage(content=summarizer_resp.content),
                state['messages'][-1]
                # last_message,
            ]
        }
    )
    return update


def sql_pre_hook(state: OrchestratorState) -> OrchestratorState:
    update: OrchestratorState = {}
    summary_model = init_chat_model(app_config.question_proc.model)
    summarier_response = summary_model.invoke(
        [
            *state["messages"],
            HumanMessage(
                content="Dựa trên lịch sử cuộc trò chuyện, tổng hợp lại thành câu hỏi trên vai của tôi để hỏi AI. Lưu ý chỉ trả về câu hỏi, không giải thích hay chú thích gì thêm."
            ),
        ]
    )
    logger.info(f"sql summary pre-hook: {summarier_response.content}")
    update.update(
        {
            "messages": [
                RemoveMessage(REMOVE_ALL_MESSAGES),
                HumanMessage(summarier_response.content),
            ]
        }
    )
    return update


async def get_orchestrator_executor(checkpointer=None) -> CompiledGraph:

    domain_conf = app_config.question_proc.domains.accountant

    domain_agent = create_react_agent(
        model=app_config.question_proc.model,
        tools=[
            get_current_date,
            get_current_time,
            create_handoff_tool(
                agent_name="orchestrator_agent",
                description="Chịu trách nhiệm xử lý câu hỏi của người dùng sau khi đã được làm rõ ý định",
            ),
        ],
        name="domain_agent",
        prompt=DomainConstant.domain_system_prompt.format(
            domain="accountant",
            knowledge=get_domain_knowledge(domain_conf.knowledge_file),
        ),
        # post_model_hook=domain_post_hook,
    )

    # domain_agent = QuestionDomainAgent(
    #     tools=[
    #         get_current_date,
    #         get_current_time,
    #     ],
    #     handoffs=[
    #         create_handoff_tool(
    #             agent_name="orchestrator_agent",
    #             description="Chịu trách nhiệm xử lý câu hỏi của người dùng sau khi đã được làm rõ ý định",
    #         )
    #     ],
    #     name="domain_agent",
    # ).graph


    async with mcp_client.session("mcp-server-text2sql") as session:
        mcp_tools = await load_mcp_tools(session)

    logger.info(f"MCP tools: {mcp_tools}")
    sql_tools = mcp_tools
    # sql_tools = [t for t in mcp_tools if getattr(t, "name") == "retrieve_data"]

    sql_generation_agent = create_react_agent(
        name="orchestrator_agent",
        model=app_config.orchestrator.model,
        tools=[*sql_tools, create_handoff_tool(agent_name="domain_agent")],
        prompt="""
        - Bạn là chuyên gia sử dụng công cụ để thực hiện tác vụ truy vấn dữ liệu. Nhiệm vụ của bạn là sử dụng sử dụng công cụ để trả lời câu hỏi của người dùng
        - Bạn chỉ được sử dụng công cụ để trả lời câu hỏi của người dùng.
        - Tuyệt đối không sử dụng dữ liệu tri thức vốn có của bạn để trả lời.
        - Tuyệt đối không cho người dùng biết về sự trao đổi giữa các agents
        """,

        # - Sau khi trả lời xong câu hỏi của người dùng về dữ liệu, chuyển giao cho `domain_agent` agent để tiếp tục luồng hoạt động.
        pre_model_hook=sql_pre_hook,
    )

    workflow = create_swarm(
        [domain_agent, sql_generation_agent],
        state_schema=OrchestratorState,
        default_active_agent="domain_agent",
    )

    # Compile and run
    app = workflow.compile(checkpointer=checkpointer)
    return app


main = main_langchain

if __name__ == "__main__":
    asyncio.run(main())
