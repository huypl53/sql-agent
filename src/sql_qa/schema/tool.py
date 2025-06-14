from typing import Any, Dict, List, Optional, TypedDict
from langgraph.graph import MessagesState
from pydantic import BaseModel


class EnhancementResponse(BaseModel):
    """
    Response model for enhancement operations.

    Attributes:
        enhanced_msg (Optional[str]): The enhanced message, if available.
        clarification_feedback (Optional[str]): Feedback or request for clarification from the enhancement process.

    Use clarification_feedback to prompt the user for more information if needed.
    """

    enhanced_msg: Optional[str]
    clarification_feedback: Optional[str]


class Text2SqlState(Text2SqlResult):
    messages: List[Dict[str, Any]]

