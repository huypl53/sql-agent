from typing import Tuple, Type

from sql_qa.config import get_app_config
from sql_qa.llm.adapter import API_MODELS, ApiAdapter, BaseAdapter, HuggingFaceAdapter
from sql_qa.llm.type import (
    SQLGenerationResponse,
    SQLQueryFixerResponse,
    SQLQueryValidationResponse,
)
from sql_qa.prompt.constant import PromptConstant

from shared.logger import get_logger

from sql_qa.prompt.template import Role

logger = get_logger(__name__, log_file=f"./logs/{__name__}.log")

app_config = get_app_config()


def get_adapter_class(model: str) -> Type[BaseAdapter]:
    if [m for m in API_MODELS if m in model]:
        return ApiAdapter
    else:
        return HuggingFaceAdapter


class LLMGeneration:
    def __init__(
        self,
        chat_config: dict,
        prompt_type: str,
        query_validation_kwargs: dict,
        query_fixer_kwargs: dict,
        generation_kwargs: dict,
    ):

        self.chat_config = chat_config
        self.tools = []
        self.prompt_type = prompt_type

        # model: str = query_validation_kwargs.get("model")
        self.query_validation_adapter = get_adapter_class(
            query_validation_kwargs.get("model")
        )(
            # model=f"{app_config.llm.provider}:{app_config.llm.model}",
            tools=self.tools,
            prompt=PromptConstant.system.format(
                dialect=app_config.database.dialect.upper()
            ),
            response_format=SQLQueryValidationResponse,
            **query_validation_kwargs,
            # checkpointer=checkpointer,
        )

        # model: str = query_fixer_kwargs.get("model")
        self.query_fixer_adapter = get_adapter_class(query_fixer_kwargs.get("model"))(
            # model=f"{app_config.llm.provider}:{app_config.llm.model}",
            tools=self.tools,
            prompt=PromptConstant.system.format(
                dialect=app_config.database.dialect.upper()
            ),
            response_format=SQLQueryFixerResponse,
            **query_fixer_kwargs,
            # checkpointer=checkpointer,
        )

        # model: str = generation_kwargs.get("model")
        self.generation_adapter = get_adapter_class(generation_kwargs.get("model"))(
            # model=f"{app_config.llm.provider}:{app_config.llm.model}",
            tools=self.tools,
            prompt=PromptConstant.system.format(
                dialect=app_config.database.dialect.upper()
            ),
            response_format=SQLGenerationResponse,
            **generation_kwargs,
        )

    def invoke(self, user_question: str, schema: str) -> Tuple[bool, str]:
        """Invokes the SQL generation process for a given user question and schema.

        This method attempts to generate a valid SQL query based on the user's question and the provided schema. It iteratively generates a SQL query, validates it, and fixes any issues up to three times. If a valid query is generated, it returns the query; otherwise, it returns an explanation of the failure.

        Args:
            user_question (str): The question posed by the user that requires a SQL query.
            schema (str): The database schema to be used for generating the SQL query.

        Returns:
            Tuple[bool, str]: A tuple containing a boolean indicating whether the generated SQL query is correct and a string representing either the final SQL query or an explanation of the failure.
        """
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
                                "content": PromptConstant.direct_generation.format(
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
                query_validation_response = self.query_validation_adapter.invoke(
                    {
                        "messages": [
                            {
                                "role": Role.ASSISTANT,
                                "content": PromptConstant.query_validation.format(
                                    question=user_question,
                                    query=sql,
                                    dialect=app_config.database.dialect.upper(),
                                ),
                            }
                        ]
                    },
                    config=self.chat_config,
                )
                if not query_validation_response:
                    logger.error(f"Query fixing response is None")
                    continue
                query_validation_result = query_validation_response["messages"][-1]
                logger.info(f"Query fixing result: {query_validation_result.content}")
                structured_query_validation_response: SQLQueryValidationResponse = (
                    query_validation_response["structured_response"]
                )
                logger.info(
                    f"Query fixing structured result: {structured_query_validation_response}"
                )
                if structured_query_validation_response.is_correct:
                    logger.info(f"Query is correct")
                    response_is_correct = True
                    generation_evidence = ""
                else:
                    logger.info(f"Query is incorrect")
                    logger.info(
                        f"Explanation: {structured_query_validation_response.explanation}"
                    )
                    generation_evidence = (
                        structured_query_validation_response.explanation
                    )
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
