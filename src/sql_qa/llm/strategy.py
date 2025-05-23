from typing import List, Tuple

from shared.logger import get_logger


from sql_qa.config import get_app_config, turn_logger
from sql_qa.llm.generation import LLMGeneration, get_adapter_class
from sql_qa.llm.type import SQLGenerationResponse
from sql_qa.prompt.constant import PromptConstant
from sql_qa.prompt.template import Role

app_config = get_app_config()

logger = get_logger(__name__)


class StategyFactory:
    def __init__(self, return_all: bool = False):
        candidate_generation_config = app_config.candidate_generations
        merger_config = app_config.merger
        self.return_all = return_all

        self.merger_adapter = (
            get_adapter_class(merger_config.model)(
                model=merger_config.model,
                tools=[],
                prompt=PromptConstant.system.format(
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

    def generate(self, user_question: str, schema: str) -> List[Tuple[bool, str]]:
        try:
            logger.info(f"Running {len(self.generators)} generators")
            results = []
            for generator in self.generators:
                is_correct, sql = generator.invoke(user_question, schema)
                logger.info(
                    f"Generator {generator.prompt_type} result: {is_correct}. Details: {sql}"
                )
                results.append((is_correct, sql))
            success_results = [r[1] for r in results if r[0]]
            if self.merger_adapter and success_results:
                merger_prompt = PromptConstant.merger.format(
                    candidates="\n".join(
                        [
                            f"Câu lệnh SQL {i+1}: " "```sql" f"{r}" "```"
                            for i, r in enumerate(success_results)
                        ]
                    )
                )
                turn_logger.log("merger_prompt", merger_prompt)
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
                logger.info(f"Merged result: {merger_structured_response}")
                return [(True, merger_structured_response.sql)]
            return results
        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            return [(False, str(e))]
