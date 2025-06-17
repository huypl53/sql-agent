from typing import List, Literal, cast
from langchain_core.messages.ai import subtract_usage
from langgraph.graph.graph import CompiledGraph
from langgraph.types import Command, Send
from shared.logger import get_logger
from shared.db import get_db, execute_sql
from sqlalchemy import update
from sqlalchemy.schema import SetConstraintComment
from sql_qa.config import get_app_config, turn_logger
from sql_qa.llm.adapter import get_react_agent
from sql_qa.llm.generation import LLMGeneration
from sql_qa.llm.type import (
    STRAT_GRAPH_NODE,
    CandidateGenState,
    SQLGenerationResponse,
    StrategyState,
)
from sql_qa.prompt.constant import Text2SqlConstant
from sql_qa.prompt.template import Role
from langgraph.graph import END, START, StateGraph

app_config = get_app_config()

logger = get_logger(__name__)


class StrategyFactory:
    def __init__(self, return_all: bool = False):
        candidate_generation_config = app_config.candidate_generations
        merger_config = app_config.merger
        self.return_all = return_all

        self.merger_adapter = get_react_agent(
            model=merger_config.model,
            tools=[],
            prompt=Text2SqlConstant.system.format(
                dialect=app_config.database.dialect.upper()
            ),
            response_format=SQLGenerationResponse,
        )

        self.generators: List[LLMGeneration] = []
        for config in candidate_generation_config:
            self.generators.append(LLMGeneration({}, **config))

        self.graph: CompiledGraph

        self._build_graph()
        self._db = get_db()

    def _build_graph(self):
        graph_builder = StateGraph(StrategyState)
        # graph_builder.add_node(STRAT_GRAPH_NODE.route, self.route_to_strategy)
        graph_builder.add_node(STRAT_GRAPH_NODE.strategy_gen, self.agenerate)
        graph_builder.add_node(STRAT_GRAPH_NODE.merge, self.merge)

        # graph_builder.add_edge(START, STRAT_GRAPH_NODE.route)
        # graph_builder.add_edge(STRAT_GRAPH_NODE.route, STRAT_GRAPH_NODE.strategy_gen)
        graph_builder.add_conditional_edges(
            START, self.route_to_strategy, [STRAT_GRAPH_NODE.strategy_gen]
        )
        graph_builder.add_edge(STRAT_GRAPH_NODE.strategy_gen, STRAT_GRAPH_NODE.merge)
        graph_builder.add_edge(STRAT_GRAPH_NODE.merge, END)

        self.graph = graph_builder.compile()

    async def agenerate(self, state: StrategyState) -> Command[Literal["merge"]]:
        strategy_name = state["strategy"]
        try:
            generator = [g for g in self.generators if g.prompt_type == strategy_name][
                0
            ]
        except:
            logger.warning(f"No strategy found for: {strategy_name}")
            return Command(goto="merge")
        gen_graph = generator.graph
        gen_payload: CandidateGenState = {}
        gen_payload.update(
            {"user_question": state["user_question"], "schema": state["schema"]}
        )
        result = await gen_graph.ainvoke(gen_payload)
        result = cast(CandidateGenState, result)

        logger.info(
            f"Generator {generator.prompt_type} result: {result['is_sql_correct']}."
            f"\nDetails: {result['sql']}. "
            f"\nExecution result: {result['execution_result']}"
        )
        result["strategy"] = generator.prompt_type

        update: StrategyState = {}
        update["logs"] = [
            {
                "strategy": strategy_name,
                "thoughts": result["correct_thoughts"],
                "sql": result["sql"],
                "execution_result": result["execution_result"],
                "is_success": bool(len(result["correct_thoughts"])),
            }
        ]

        return Command(
            goto="merge",
            update=update,
        )

    def merge(self, state: StrategyState) -> Command[Literal[END]]:
        logs = state["logs"]
        if not len(logs):
            return Command(goto=END)

        success_sqls = [s["sql"] for s in logs]
        merger_prompt = Text2SqlConstant.merger.format(
            candidates="\n".join(
                [
                    (f"Câu lệnh SQL {i+1}: " "\n```sql\n" f"{r}" "\n```")
                    for i, r in enumerate(success_sqls)
                ]
            )
        )
        turn_logger.log("merger_prompt", merger_prompt)
        try:
            merger_response = self.merger_adapter.invoke(
                {
                    "messages": [
                        {
                            "role": Role.ASSISTANT,
                            "content": merger_prompt,
                        }
                    ]
                }
            )
            turn_logger.log(
                "merger_response",
                f" {merger_response['structured_response'] if merger_response else 'None'}",
            )

            merger_structured_response: SQLGenerationResponse = merger_response[
                "structured_response"
            ]
        except Exception as e:
            logger.error(f"Error merging SQL: {e}")
            turn_logger.log("merger_error", str(e))
            return Command(goto=END)
        logger.info(f"Merged result: {merger_structured_response}")
        turn_logger.log("merger_result", merger_structured_response)
        update: StrategyState = {}
        sql = merger_structured_response["sql"]
        exec_result, is_success = execute_sql(self._db, sql)
        update.update(
            {
                "": "",

                "logs": [
                    {
                        "strategy": STRAT_GRAPH_NODE.merge,
                        "sql": sql,
                        "thoughts": [
                            {
                                "name": STRAT_GRAPH_NODE.merge,
                                "value": merger_structured_response["explaination"],
                            }
                        ],
                        "execution_result": exec_result,
                        "is_success": is_success,
                    }
                ]
            }
        )
        return Command(goto=END, update=update)

    def route_to_strategy(
        self, state: StrategyState
    ) -> Literal[STRAT_GRAPH_NODE.strategy_gen]:
        logger.info(f"Running {len(self.generators)} generators")

        return [
            Send(STRAT_GRAPH_NODE.strategy_gen, {**state, "strategy": s.prompt_type})
            for s in self.generators
        ]


if __name__ == "__main__":

    generator = StrategyFactory()
    graph = generator.graph
    with open("./tmp/strategy_graph.png", "wb") as fw:
        fw.write(graph.get_graph().draw_mermaid_png())
