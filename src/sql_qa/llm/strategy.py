from typing import List, Tuple

from shared.logger import get_logger


from sql_qa.config import get_app_config, turn_logger
from sql_qa.llm.adapter import get_react_agent
from sql_qa.llm.generation import LLMGeneration
from sql_qa.llm.type import GenerationResult, SQLGenerationResponse
from sql_qa.prompt.constant import Text2SqlConstant
from sql_qa.prompt.template import Role

app_config = get_app_config()

logger = get_logger(__name__)


class StategyFactory:
    def __init__(self, return_all: bool = False):
        candidate_generation_config = app_config.candidate_generations
        merger_config = app_config.merger
        self.return_all = return_all

        self.merger_adapter = (
            get_react_agent(
                model=merger_config.model,
                tools=[],
                prompt=Text2SqlConstant.system.format(
                    dialect=app_config.database.dialect.upper()
                ),
                response_format=SQLGenerationResponse,
            )
            if not return_all
            else None
        )

        self.generators: List[LLMGeneration] = []
        for config in candidate_generation_config:
            self.generators.append(LLMGeneration({}, **config.model_dump()))

    def generate(self, user_question: str, schema: str) -> List[GenerationResult]:
        try:
            logger.info(f"Running {len(self.generators)} generators")
            results: List[GenerationResult] = []
            for generator in self.generators:
                result = generator.invoke(user_question, schema)
                logger.info(
                    f"Generator {generator.prompt_type} result: {result.is_correct}."
                    f"\nDetails: {result.sql}. "
                    f"\nExecution result: {result.execution_result}"
                )
                results.append(result)
            results = sorted(results, key=lambda x: x.is_correct, reverse=True)
            success_sqls = [r.sql for r in results if r.is_correct]
            if self.merger_adapter and success_sqls:
                merger_prompt = Text2SqlConstant.merger.format(
                    candidates="\n".join(
                        [
                            f"Câu lệnh SQL {i+1}: " "```sql\n" f"{r}" "```"
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
                    return results
                logger.info(f"Merged result: {merger_structured_response}")
                turn_logger.log("merger_result", merger_structured_response)
                return [
                    GenerationResult(
                        sql=merger_structured_response.sql,
                        execution_result=None,
                        is_correct=True,
                    )
                ]
            return results
        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            return [
                GenerationResult(
                    is_correct=False,
                    execution_result=str(e),
                    sql=None,
                )
            ]
