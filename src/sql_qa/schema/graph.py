from typing import Annotated, Callable, Coroutine, List, Optional, Any, TypedDict
from langchain_core.messages import AnyMessage

from sql_qa.prompt.template import Role
from functools import wraps
from operator import add


def reduce_messages_turn(
    left: List[AnyMessage], right: List[AnyMessage]
) -> List[AnyMessage]:
    # logger.info(f"Left: {left}, Right: {right}")
    for msg in right:
        if hasattr(msg, "role") and msg.role == Role.USER:
            return right
    return left + right


class EnhancementState(TypedDict):
    messages: Annotated[List[AnyMessage], reduce_messages_turn]
    tool_results: List[Any]
    user_question: Optional[str]
    
class SupervisorState(EnhancementState):
    messages: Annotated[List[AnyMessage], add]


GRAPH_TOOL_INPUT = (
    Callable[[EnhancementState | str], Coroutine[None, None, Any]]
    | Callable[[EnhancementState | str], Any]
)


def graph_tool(
    func: GRAPH_TOOL_INPUT,
) -> GRAPH_TOOL_INPUT:
    """
    Decorator to mark a function as a graph tool.
    """

    # sig = inspect.signature(func)
    @wraps(func)
    def wrapper(*args, **kwargs):
        # if type(args[0]) is EnhancementState:
        #     # If the first argument is EnhancementState, we assume it's a graph tool
        #     return func(*args, **kwargs)
        return func(*args, **kwargs)

    return wrapper
