import asyncio
import operator
from typing import (
    Annotated,
    Callable,
    Literal,
    NamedTuple,
    TypedDict,
    Dict,
    List,
    Union,
)

from langchain_core.runnables import Runnable
from langchain_core.tools.base import BaseTool
from typing import Any
from langchain_core.messages import AnyMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import MessagesState
from langgraph.graph.graph import CompiledGraph
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from sql_qa.agent.base import AgentBase, AgentBaseState
from sql_qa.config import get_app_config
from sql_qa.llm.adapter import get_react_agent
from shared.logger import logger

from sql_qa.prompt.constant import DomainConstant
from sql_qa.prompt.template import Role

type TQuestionDomain = Literal["accountant"]
app_config = get_app_config()


class QUESTION_PROC_NODE(NamedTuple):
    route = "route_node"
    proc = "proc_node"


class QuestionDomainAgentState(AgentBaseState):
    # messages: Annotated[List[AnyMessage], operator.add]
    domain: TQuestionDomain
    pass


QU_NODE = QUESTION_PROC_NODE


def get_domain_knowledge(knowledge_file: str) -> Any:
    try:
        with open(knowledge_file, "r", encoding="utf-8") as fr:
            logger.info(f"Read knowledge for domain {knowledge_file} succesfully!")
            return fr.read()
    except Exception as e:
        logger.error(
            f"Get error when reading knowledge of {knowledge_file}. Returning empty. Error: {e}"
        )
        return ""


class QuestionDomainAgent(AgentBase):
    def __init__(
        self,
        tools: List[Callable],
        handoffs: List[BaseTool],
        name: str = "domain_agent",
    ) -> None:
        super().__init__(tools, handoffs, name)

    def _build_graph(self):
        agent_tools = [*self._tools, *self._handoffs]
        logger.info(f"Agent tools: {agent_tools}")
        self.domain_agents: Dict[str, CompiledGraph] = {
            k: create_react_agent(
                app_config.question_proc.model,
                tools=agent_tools,
                prompt=DomainConstant.domain_system_prompt.format(
                    domain=k, knowledge=get_domain_knowledge(f["knowledge_file"])
                ),
            )
            for k, f in app_config.question_proc.domains.items()
        }
        # get_react_agent(app_config.question_proc.model)
        self.domain_knowledge: Dict[str, str] = {
            k: get_domain_knowledge(f["knowledge_file"])
            for k, f in app_config.question_proc.domains.items()
        }

        graph_builder = StateGraph(QuestionDomainAgentState)
        # graph_builder.add_node(NODE.route, self.route_domain_proc)
        graph_builder.add_node(
            QU_NODE.proc,
            self.process_question,
            destinations=self.handoff_nodes,
        )

        for ho_node in self._handoff_nodes:
            graph_builder.add_node(ho_node.name, ho_node)

        graph_builder.add_edge(START, QU_NODE.proc)
        graph_builder.add_edge(QU_NODE.proc, END)

        return graph_builder.compile(name=self._name)

    async def process_question(
        self, state: QuestionDomainAgentState
    ) -> Command[Literal[END]]:
        domain = state["domain"]
        update: QuestionDomainAgentState = {}
        if domain not in self.domain_agents:
            logger.warning(f"Domain {domain} not loaded!\nCheck knowledge_file")
            return Command(goto=END, update=update)
        agent = self.domain_agents[domain]
        try:
            domain_agent_resp = await agent.ainvoke({"messages": state["messages"]})
            last_message = domain_agent_resp["messages"][-1]
            update.update({"messages": [last_message]})
            # if type(last_message) == ToolMessage:
            #     return Command(goto=state['active_agent'], graph=Command.PARENT, update=update)

        except Exception as e:
            logger.warning(f"Domain {domain} enhance question failed!\n Error: {e}")

        return Command(goto=END, update=update)


if __name__ == "__main__":
    agent = QuestionDomainAgent()
    graph = agent.graph
    question = "cho tôi sản phẩm best-seller tháng 4"

    async def arun():
        print(f"Original question: \n```{question}```")
        payload: QuestionDomainAgentState = {
            "messages": [HumanMessage(content=question)],
            "domain": "accountant",
        }
        enhanced_question = await graph.ainvoke(payload)
        print(f"enhanced_question: \n ```{enhanced_question}```")
        return enhanced_question

    asyncio.run(arun())
