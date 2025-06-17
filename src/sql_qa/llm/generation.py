from typing import Literal, Optional, Tuple, Dict, Any, cast, Union
from langgraph.graph import END, START, StateGraph
from langgraph.graph.graph import CompiledGraph
from langgraph.types import Command
from shared.db import get_db
from sql_qa.config import get_app_config
from sql_qa.llm.adapter import get_react_agent
from sql_qa.llm.type import (
    GRAPH_NODE,
    CandidateGenState,
    SQLGenerationResponse,
    SQLQueryFixerResponse,
    SQLQueryValidationResponse,
)
from sql_qa.prompt.constant import Text2SqlConstant

from shared.logger import get_logger
from sql_qa.config import turn_logger

from sql_qa.prompt.template import Role

logger = get_logger(__name__)

app_config = get_app_config()


_MAX_GEN_TIME = 3


class LLMGeneration:
    def __init__(
        self,
        chat_config: dict,
        prompt_type: str,
        query_validation_kwargs: dict,
        query_fixer_kwargs: dict,
        generation_kwargs: dict,
    ):

        self.db = get_db()
        self.chat_config = chat_config
        self.tools = []
        self.prompt_type = prompt_type
        self.graph: CompiledGraph

        # model: str = query_validation_kwargs.get("model")
        self.query_validation_adapter = get_react_agent(
            tools=self.tools,
            prompt=Text2SqlConstant.system.format(
                dialect=app_config.database.dialect.upper()
            ),
            response_format=SQLQueryValidationResponse,
            **query_validation_kwargs,
        )

        # model: str = query_fixer_kwargs.get("model")
        self.query_fixer_adapter = get_react_agent(
            tools=self.tools,
            prompt=Text2SqlConstant.system.format(
                dialect=app_config.database.dialect.upper()
            ),
            response_format=SQLQueryFixerResponse,
            **query_fixer_kwargs,
            # checkpointer=checkpointer,
        )

        # model: str = generation_kwargs.get("model")
        self.generation_adapter = get_react_agent(
            tools=self.tools,
            prompt=Text2SqlConstant.system.format(
                dialect=app_config.database.dialect.upper()
            ),
            response_format=SQLGenerationResponse,
            **generation_kwargs,
        )

        self._build_graph()

    def _build_graph(self):
        graph_builder = StateGraph(CandidateGenState)
        graph_builder.add_node(GRAPH_NODE.init, self.init_state)
        graph_builder.add_node(GRAPH_NODE.route, self.route)
        graph_builder.add_node(GRAPH_NODE.candidate, self.gen_candidate)
        graph_builder.add_node(GRAPH_NODE.validate, self.validate_generation)
        graph_builder.add_node(GRAPH_NODE.should_fix, self.should_fix)
        graph_builder.add_node(GRAPH_NODE.fix, self.fix_query)

        graph_builder.add_edge(START, GRAPH_NODE.init)
        graph_builder.add_edge(GRAPH_NODE.init, GRAPH_NODE.route)
        graph_builder.add_edge(GRAPH_NODE.route, GRAPH_NODE.candidate)
        graph_builder.add_edge(GRAPH_NODE.candidate, GRAPH_NODE.validate)
        graph_builder.add_edge(GRAPH_NODE.validate, GRAPH_NODE.should_fix)
        graph_builder.add_edge(GRAPH_NODE.should_fix, END)

        self.graph = graph_builder.compile()

    def init_state(self, state: CandidateGenState) -> CandidateGenState:
        return {
            "run_iter": 0,
            "explaination": "",
            "logs": [],
            "is_sql_correct": False,
            "execution_result": "",
            "sql": "",
            "user_question": state["user_question"],
            "schema": state["schema"],
            "enhanced_result": "",
            "is_execution_correct": False,
            "strategy": self.prompt_type,
        }

    def route(
        self, state: CandidateGenState
    ) -> Command[Union[Literal["candidate"], str]]:
        """Route graph and update run iter, exit graph if reach MAX iters"""
        schema = state["schema"]
        run_iter = state["run_iter"]
        run_iter += 1
        update: CandidateGenState = {}
        update["run_iter"] = run_iter

        last_log = state["logs"][-1] if state["logs"] else None
        update["evidence"] = (
            (
                "---"
                f"chuyên gia `{last_log['name']}` cho rằng hệ thống bị lỗi do: {last_log['value']} "
                "---"
            )
            if last_log
            else ""
        )

        if run_iter > _MAX_GEN_TIME:
            return Command(goto=END, update=update)
        else:
            return Command(update=update, goto=GRAPH_NODE.candidate)

    def gen_candidate(
        self, state: CandidateGenState
    ) -> Command[Literal["route", "validate"]]:
        user_question = state["user_question"]
        schema = state["schema"]
        evidences = state["logs"][-1:]
        gen_evidence = ""
        if evidences:
            gen_evidence = (
                "---"
                f"*Ở bước `{evidences[0]['name']}`, phát hiện lỗi sau:*"
                f"{evidences[0]['value']}"
                "```"
                "---"
            )
        prompt_template = getattr(Text2SqlConstant, self.prompt_type)
        generation_prompt = prompt_template.format(
            question=user_question,
            evidence=gen_evidence,
            schema=schema,
        )
        turn_logger.log(
            f"{self.prompt_type}_prompt",
            f"---retry--- \n" f" {generation_prompt}",
        )
        logger.info(f"Generation with strategy: {self.prompt_type}")
        generation_response = self.generation_adapter.invoke(
            {
                "messages": [
                    {
                        "role": Role.USER,
                        "content": generation_prompt,
                    }
                ]
            },
            config=self.chat_config,
        )
        turn_logger.log(
            f"{self.prompt_type}_generation_response",
            f"---retry--- \n"
            f" {generation_response['structured_response'] if generation_response else 'None'}",
        )
        # LLM Error maybe
        if not generation_response:
            logger.error(f"Generation response is None")
            return Command(
                goto="route", update={"error": "Generation response is None"}
            )

        generation_result = generation_response["messages"][-1]
        logger.info(f"SQL Generation result: {generation_result.content}")
        logger.info(
            f"SQL Generation structured result: {generation_response['structured_response']}"
        )
        structured_generation_response: SQLGenerationResponse = generation_response[
            "structured_response"
        ]
        sql = structured_generation_response["sql"]
        explaination = structured_generation_response["explaination"]
        logger.info(f"SQL: {sql}")
        logger.info(f"explaination: {explaination}")
        return Command(
            goto="validate",
            update={
                "sql": sql,
                "explaination": explaination,
                "logs": [
                    {
                        "name": f"{self.prompt_type}_{GRAPH_NODE.candidate}",
                        "value": structured_generation_response,
                    }
                ],
                "correct_thoughts": [
                    {
                        "name": f"{self.prompt_type}_{GRAPH_NODE.candidate}",
                        "value": structured_generation_response,
                    }
                ],
            },
        )

    def validate_generation(
        self, state: CandidateGenState
    ) -> Command[Literal["route", "should_fix"]]:
        user_question = state["user_question"]
        sql = state["sql"]
        query_validation_prompt = Text2SqlConstant.query_validation.format(
            question=user_question,
            query=sql,
            dialect=app_config.database.dialect.upper(),
        )
        turn_logger.log(
            "query_validation_prompt",
            f"---retry--- \n" f" {query_validation_prompt}",
        )

        query_validation_response = self.query_validation_adapter.invoke(
            {
                "messages": [
                    {
                        "role": Role.USER,
                        "content": query_validation_prompt,
                    }
                ]
            },
            config=self.chat_config,
        )
        turn_logger.log(
            "query_validation_response",
            f"---retry--- \n"
            f" {query_validation_response['structured_response'] if query_validation_response else 'None'}",
        )
        if not query_validation_response:
            logger.error(f"Query validation response is None")
            return Command(
                goto="route", update={"error": "Query validation response is None"}
            )
        query_validation_result = query_validation_response["messages"][-1]
        logger.info(f"Query validation result: {query_validation_result.content}")
        structured_query_validation_response: SQLQueryValidationResponse = (
            query_validation_response["structured_response"]
        )
        logger.info(
            f"Query validation structured result: {structured_query_validation_response}"
        )
        is_sql_correct, explaination = structured_query_validation_response
        if is_sql_correct:
            return Command(
                goto="should_fix",
                update={
                    "logs": [
                        {
                            "name": GRAPH_NODE.validate,
                            "value": explaination,
                        }
                    ],
                    "correct_thoughts": [
                        {
                            "name": GRAPH_NODE.validate,
                            "value": structured_query_validation_response,
                        }
                    ],
                },
            )

        return Command(
            goto="route",
            update={
                "logs": [
                    {
                        "name": GRAPH_NODE.validate,
                        "value": structured_query_validation_response,
                    }
                ]
            },
        )

    def should_fix(self, state: CandidateGenState) -> Command[Literal[END, "fix"]]:
        execution_result, execution_result_is_sql_correct = self.execute_sql(
            state["sql"]
        )
        updates = (
            {
                "execution_result": execution_result,
                "is_sql_correct": execution_result_is_sql_correct,
            },
        )

        if not execution_result_is_sql_correct:
            return Command(
                goto=GRAPH_NODE.fix,
                update=updates,
            )

        return Command(
            goto=END,
            update=updates,
        )

    def fix_query(self, state: CandidateGenState) -> Command[Literal["route", END]]:
        schema = state["schema"]
        user_question = state["user_question"]
        evidence = state["explaination"]
        sql = state["sql"]
        execution_result = state["execution_result"]
        query_fixing_prompt = Text2SqlConstant.query_fixing.format(
            schema=schema,
            question=user_question,
            evidence=evidence,
            query=sql,
            result=execution_result,
        )
        turn_logger.log(
            "query_fixing_prompt",
            f"---retry--- \n" f" {query_fixing_prompt}",
        )
        query_fixing_response = self.query_fixer_adapter.invoke(
            {
                "messages": [
                    {
                        "role": Role.USER,
                        "content": query_fixing_prompt,
                    }
                ]
            },
            config=self.chat_config,
        )
        if not query_fixing_response:
            logger.error(f"Query fixing response is None")
            return Command(
                goto="route",
                update={
                    "error": "Query fixing response is None",
                },
            )
        query_fixing_result = query_fixing_response["messages"][-1]
        logger.info(f"Query fixing result: {query_fixing_result.content}")
        structured_query_fixing_response: SQLQueryFixerResponse = query_fixing_response[
            "structured_response"
        ]
        logger.info(
            f"Query fixing structured result: {structured_query_fixing_response}"
        )
        turn_logger.log(
            "query_fixing_response",
            f"---retry--- \n" f" {query_fixing_response['structured_response']}",
        )
        sql, fix_explaination = structured_query_fixing_response

        exec_result, is_success = self.execute_sql(sql)
        run_iter = state["run_iter"]
        update = {
            "run_iter": run_iter + 1,
            "sql": sql,
            "explaination": fix_explaination,
            "execution_result": exec_result,
            "logs": [
                {
                    "name": GRAPH_NODE.fix,
                    "value": (
                        f"{ structured_query_fixing_response}" "---" f"{exec_result}"
                    ),
                }
            ],
            "correct_thoughts": (
                [
                    {
                        "name": GRAPH_NODE.fix,
                        "value": (
                            f"{ structured_query_fixing_response}"
                            "---"
                            f"{exec_result}"
                        ),
                    }
                ]
                if is_success
                else []
            ),
        }
        if not is_success and run_iter < _MAX_GEN_TIME:
            return Command(
                goto=GRAPH_NODE.fix,
                update=update,
            )
        return Command(goto=END, update=update)

    def execute_sql(self, sql: str) -> Tuple[Any, bool]:
        """
        Return:
            execution_result [Any]
            is_success [bool]
        """
        try:
            execution_result = self.db.run(sql)
            return execution_result, True
        except Exception as e:
            return str(e), False


if __name__ == "__main__":
    generator = LLMGeneration({}, **app_config.candidate_generations[0])
    graph = generator.graph
    with open("./tmp/candidate_generation.png", "wb") as fw:
        fw.write(graph.get_graph().draw_mermaid_png())
