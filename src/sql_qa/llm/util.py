from shared.logger import get_logger
from tenacity import RetryCallState

logger = get_logger(__name__, log_file=f"./logs/{__name__}.log")


def on_llm_retry_fail(retry_state: RetryCallState) -> None:

    try:
        logger.error(
            str(
                f"Last run result: {hasattr(retry_state.outcome, 'result') and retry_state.outcome.result}\nException: { retry_state.outcome and retry_state.outcome.exception() }"
            )
        )
    except Exception as e:
        logger.error(str(e))
