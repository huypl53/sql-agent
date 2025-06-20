import asyncio
from typing import Literal, Optional, NamedTuple, TypedDict, Dict

from typing import Any
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from sql_qa.config import get_app_config
from sql_qa.llm.adapter import get_react_agent
from shared.logger import logger

from sql_qa.prompt.constant import DomainConstant
from sql_qa.prompt.template import Role

type TQuestionDomain = Literal["accountant"]


class QUESTION_PROC_NODE(NamedTuple):
    route = "route_node"
    proc = "proc_node"


class QuestionDomainAgentState(TypedDict):
    user_question: str
    domain: TQuestionDomain
    knowledge: Optional[str]
    enhanced_question: str
    pass


NODE = QUESTION_PROC_NODE

app_config = get_app_config()


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


class QuestionDomainAgent:
    def __init__(self) -> None:
        self.graph = self._build_graph()
        self.domain_agent = get_react_agent(app_config.question_proc.model)
        self.domain_knowledge: Dict[str, str] = {
            k: get_domain_knowledge(f["knowledge_file"])
            for k, f in app_config.question_proc.domains.items()
        }

        self.graph = self._build_graph()

    def _build_graph(self):
        graph_builder = StateGraph(QuestionDomainAgentState)
        # graph_builder.add_node(NODE.route, self.route_domain_proc)
        graph_builder.add_node(NODE.proc, self.process_question)

        graph_builder.add_edge(START, NODE.proc)
        graph_builder.add_edge(NODE.proc, END)

        return graph_builder.compile()

    async def process_question(self, state: QuestionDomainAgentState) -> Command[END]:
        domain = state["domain"]
        update: QuestionDomainAgentState = {**state}
        if domain not in self.domain_knowledge:
            update["enhanced_question"] = ""
            logger.warning(f"Domain {domain} not loaded!\nCheck knowledge_file")
            return Command(goto=END, update=update)
        knowledge = self.domain_knowledge[domain]
        update.update({"knowledge": knowledge})
        domain_prompt = DomainConstant.refine_prompt.format(
            domain=domain, question=state["user_question"], knowledge=knowledge
        )
        try:
            domain_agent_resp = await self.domain_agent.ainvoke(
                {"messages": [{"role": Role.USER, "content": domain_prompt}]}
            )
            domain_agent_result: str = domain_agent_resp["messages"][-1].content
        except Exception as e:
            logger.warning(f"Domain {domain} enhance question failed!\n Error: {e}")
            domain_agent_result = ""

        update.update({"enhanced_question": domain_agent_result})

        return Command(goto=END, update=update)


if __name__ == "__main__":
    agent = QuestionDomainAgent()
    graph = agent.graph
    question = "cho tôi sản phẩm best-seller tháng 4"

    async def arun():
        print(f"Original question: \n```{question}```")
        payload: QuestionDomainAgentState = {}
        payload.update(user_question=question, domain="accountant")
        enhanced_question = await graph.ainvoke(payload)
        print(f"enhanced_question: \n ```{enhanced_question}```")
        return enhanced_question

    asyncio.run(arun())
