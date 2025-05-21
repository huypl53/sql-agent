from abc import ABC, abstractmethod
from typing import Tuple

from sql_qa.config import Settings, get_app_config
from sql_qa.llm.adapter import ApiAdapter, BaseAdapter
from sql_qa.llm.type import SQLGenerationResponse, SQLQueryFixingResponse
from sql_qa.prompt.constant import PromptConstant

from shared.logger import get_logger

from sql_qa.prompt.template import Role

logger = get_logger(__name__, log_file=f"./logs/{__name__}.log")

app_config = get_app_config()


class LLMBaseGeneration(ABC):
    def __init__(self, chat_config: dict):
        self.chat_config = chat_config
        self.tools = []

        self.query_fixing_adapter = ApiAdapter(
            model=f"{app_config.llm.provider}:{app_config.llm.model}",
            tools=self.tools,
            prompt=PromptConstant.system_prompt.format(
                dialect=app_config.database.dialect.upper()
            ),
            response_format=SQLQueryFixingResponse,
            # checkpointer=checkpointer,
        )

        self.generation_adapter: BaseAdapter = None

    @abstractmethod
    def invoke(self, query: str, schema: str, llm: BaseAdapter) -> str:
        pass


class LLMDirectGeneration(LLMBaseGeneration):
    def __init__(self, chat_config: dict):
        super().__init__(chat_config)

        self.generation_adapter = ApiAdapter(
            model=f"{app_config.llm.provider}:{app_config.llm.model}",
            tools=self.tools,
            prompt=PromptConstant.system_prompt.format(
                dialect=app_config.database.dialect.upper()
            ),
            response_format=SQLGenerationResponse,
            # checkpointer=checkpointer,
            # pre_model_hook=trimmer,
        )

    def invoke(self, user_question: str, schema: str) -> Tuple[bool, str]:
        try:
            run_iter = 0
            response_is_correct = False
            generation_evidence = ""
            final_sql = ""
            while run_iter < 3 and not response_is_correct:
                logger.info(
                    f"Run iteration: {run_iter}; Evidence: {generation_evidence}; Response is correct: {response_is_correct}"
                )
                run_iter += 1
                generation_response = self.generation_adapter.invoke(
                    {
                        "messages": [
                            {
                                "role": Role.ASSISTANT,
                                "content": PromptConstant.direct_generation_prompt.format(
                                    question=user_question,
                                    evidence=generation_evidence,
                                    schema=schema,
                                ),
                            }
                        ]
                    },
                    config=self.chat_config,
                )
                if not generation_response:
                    logger.error(f"Generation response is None")
                    continue
                generation_result = generation_response["messages"][-1]
                logger.info(f"SQL Generation result: {generation_result.content}")
                logger.info(
                    f"SQL Generation structured result: {generation_response['structured_response']}"
                )
                structured_generation_response: SQLGenerationResponse = (
                    generation_response["structured_response"]
                )
                sql = structured_generation_response.sql
                final_sql = sql
                logger.info(f"SQL: {sql}")
                logger.info(
                    f"Explanation: {structured_generation_response.explanation}"
                )

                # response_is_correct = True
                # break
                query_fixing_response = self.query_fixing_adapter.invoke(
                    {
                        "messages": [
                            {
                                "role": Role.ASSISTANT,
                                "content": PromptConstant.query_fixing_prompt.format(
                                    question=user_question,
                                    query=sql,
                                    dialect=app_config.database.dialect.upper(),
                                ),
                            }
                        ]
                    },
                    config=self.chat_config,
                )
                if not query_fixing_response:
                    logger.error(f"Query fixing response is None")
                    continue
                query_fixing_result = query_fixing_response["messages"][-1]
                logger.info(f"Query fixing result: {query_fixing_result.content}")
                structured_query_fixing_response: SQLQueryFixingResponse = (
                    query_fixing_response["structured_response"]
                )
                logger.info(
                    f"Query fixing structured result: {structured_query_fixing_response}"
                )
                if structured_query_fixing_response.is_correct:
                    logger.info(f"Query is correct")
                    response_is_correct = True
                else:
                    logger.info(f"Query is incorrect")
                    logger.info(
                        f"Explanation: {structured_query_fixing_response.explanation}"
                    )
                    generation_evidence = structured_query_fixing_response.explanation
                    response_is_correct = False

            logger.info(f"Final SQL: {final_sql}")
            if not response_is_correct:
                logger.info(
                    f"Final resposne is correct: {response_is_correct}; Final explanation: {generation_evidence}"
                )
                print("Query is incorrect, please try again.")
                return False, generation_evidence
            logger.info(
                f"Final resposne is correct: {response_is_correct}; Final explanation: {generation_evidence}"
            )
            return True, final_sql

        except Exception as e:
            logger.error(f"Error: {e}")
            return False, str(e)
