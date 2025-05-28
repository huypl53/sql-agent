from typing import Optional, Tuple

from shared.db import get_db
from sql_qa.config import get_app_config
from sql_qa.llm.adapter import get_adapter_class
from sql_qa.llm.type import (
    GenerationResult,
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

        # model: str = query_validation_kwargs.get("model")
        self.query_validation_adapter = get_adapter_class(
            query_validation_kwargs.get("model")
        )(
            # model=f"{app_config.llm.provider}:{app_config.llm.model}",
            tools=self.tools,
            prompt=Text2SqlConstant.system.format(
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
            prompt=Text2SqlConstant.system.format(
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
            prompt=Text2SqlConstant.system.format(
                dialect=app_config.database.dialect.upper()
            ),
            response_format=SQLGenerationResponse,
            **generation_kwargs,
        )

    def invoke(self, user_question: str, schema: str) -> GenerationResult:
        """Invokes the SQL generation process for a given user question and schema.

        This method attempts to generate a valid SQL query based on the user's question and the provided schema. It iteratively generates a SQL query, validates it, and fixes any issues up to three times. If a valid query is generated, it returns the query; otherwise, it returns an explanation of the failure.

        Args:
            user_question (str): The question posed by the user that requires a SQL query.
            schema (str): The database schema to be used for generating the SQL query.

        Returns:
            Tuple[bool, str]: A tuple containing a boolean indicating whether the generated SQL query is correct and a string representing either the final SQL query or an explanation of the failure.
        """
        try:
            turn_logger.log
            run_iter = 0
            sql_is_correct = False
            execution_result_is_correct = False
            generation_evidence = ""
            final_sql = ""
            execution_result = ""
            while (
                run_iter < 3 and not sql_is_correct and not execution_result_is_correct
            ):
                logger.info(
                    f"Run iteration: {run_iter}; Evidence: {generation_evidence}; Response is correct: {sql_is_correct}"
                )
                run_iter += 1
                prompt_template = getattr(Text2SqlConstant, self.prompt_type)
                generation_prompt = prompt_template.format(
                    question=user_question,
                    evidence=generation_evidence,
                    schema=schema,
                )
                turn_logger.log(
                    f"{self.prompt_type}_prompt",
                    f"---retry {run_iter}--- \n" f" {generation_prompt}",
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
                    "generation_response",
                    f"---retry {run_iter}--- \n"
                    f" {generation_response['structured_response'] if generation_response else 'None'}",
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
                query_validation_prompt = Text2SqlConstant.query_validation.format(
                    question=user_question,
                    query=sql,
                    dialect=app_config.database.dialect.upper(),
                )
                turn_logger.log(
                    "query_validation_prompt",
                    f"---retry {run_iter}--- \n" f" {query_validation_prompt}",
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
                    f"---retry {run_iter}--- \n"
                    f" {query_validation_response['structured_response'] if query_validation_response else 'None'}",
                )
                if not query_validation_response:
                    logger.error(f"Query validation response is None")
                    continue
                query_validation_result = query_validation_response["messages"][-1]
                logger.info(
                    f"Query validation result: {query_validation_result.content}"
                )
                structured_query_validation_response: SQLQueryValidationResponse = (
                    query_validation_response["structured_response"]
                )
                logger.info(
                    f"Query validation structured result: {structured_query_validation_response}"
                )
                if structured_query_validation_response.is_correct:
                    logger.info(f"Query is correct")
                    sql_is_correct = True
                    generation_evidence = ""
                else:
                    logger.info(f"Query is incorrect")
                    logger.info(
                        f"Explanation: {structured_query_validation_response.explanation}"
                    )
                    generation_evidence = (
                        structured_query_validation_response.explanation
                    )
                    sql_is_correct = False
                    continue

                logger.info(f"Final SQL: {final_sql}")
                if not sql_is_correct:
                    logger.info(
                        f"Final resposne is correct: {sql_is_correct}; Final explanation: {generation_evidence}"
                    )
                    print("Query is incorrect, please try again.")
                    # return False, generation_evidence, None
                    return GenerationResult(
                        sql=final_sql,
                        execution_result=generation_evidence,
                        is_correct=False,
                    )
                logger.info(
                    f"Final resposne is correct: {sql_is_correct}; Final explanation: {structured_query_validation_response.explanation}"
                )
                turn_logger.log(
                    "final_sql",
                    f"---retry {run_iter}--- \n" f" {final_sql}",
                )

                # Execute query
                execution_result, execution_result_is_correct = self.execute_sql(
                    final_sql
                )
                if not execution_result_is_correct:
                    query_fixing_prompt = Text2SqlConstant.query_fixing.format(
                        schema=schema,
                        question=user_question,
                        evidence=generation_evidence,
                        query=final_sql,
                        result=execution_result,
                    )
                    turn_logger.log(
                        "query_fixing_prompt",
                        f"---retry {run_iter}--- \n" f" {query_fixing_prompt}",
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
                        continue
                    query_fixing_result = query_fixing_response["messages"][-1]
                    logger.info(f"Query fixing result: {query_fixing_result.content}")
                    structured_query_fixing_response: SQLQueryFixerResponse = (
                        query_fixing_response["structured_response"]
                    )
                    logger.info(
                        f"Query fixing structured result: {structured_query_fixing_response}"
                    )
                    final_sql = structured_query_fixing_response.sql
                    # generation_evidence = structured_query_fixing_response.explanation
                    turn_logger.log(
                        "query_fixing_response",
                        f"---retry {run_iter}--- \n"
                        f" {query_fixing_response['structured_response']}",
                    )
                    execution_result, execution_result_is_correct = self.execute_sql(
                        final_sql
                    )
                    continue
                else:
                    execution_result_is_correct = True

                logger.info(f"Execution result: {execution_result}")

            return GenerationResult(
                sql=final_sql,
                execution_result=execution_result,
                is_correct=execution_result_is_correct,
            )

        except Exception as e:
            logger.error(f"Error: {str( e )}")
            return GenerationResult(
                sql=None,
                execution_result=str(e),
                is_correct=False,
            )

    def execute_sql(self, sql: str) -> Tuple[str, bool]:
        try:
            execution_result = self.db.run(sql)
            return execution_result, True
        except Exception as e:
            return str(e), False
