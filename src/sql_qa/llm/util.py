from shared.logger import logger
from tenacity import RetryCallState


def on_llm_retry_fail(retry_state: RetryCallState) -> None:

    try:
        logger.error(
            str(
                f"Last run result: {hasattr(retry_state.outcome, 'result') and retry_state.outcome.result}\nException: { retry_state.outcome and retry_state.outcome.exception() }"
            )
        )
    except Exception as e:
        logger.error(str(e))
