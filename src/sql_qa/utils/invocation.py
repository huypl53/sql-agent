from typing import Any, Dict, List
from langgraph.graph.graph import CompiledGraph
import tenacity
from sql_qa.llm.util import on_llm_retry_fail
from shared.logger import get_logger

logger = get_logger(__name__)


@tenacity.retry(
    stop=tenacity.stop_after_attempt(1),
    wait=tenacity.wait_exponential(multiplier=1, min=7, max=60),
    retry=tenacity.retry_if_exception_type(Exception),
    reraise=True,
    retry_error_callback=on_llm_retry_fail,
    before=lambda retry_state: (
        logger.warning(
            f"Retry attempt {retry_state.attempt_number} due to error: {retry_state.outcome.exception()}"
        )
        if retry_state.outcome
        else logger.warning(
            f"Retry attempt {retry_state.attempt_number} due to unknown error"
        )
    ),
)
async def ainvoke_agent(
    agent_executor: CompiledGraph,
    messages: Dict[str, List[Any]],
    config: dict | None = None,
):
    return await agent_executor.ainvoke(messages, config)
