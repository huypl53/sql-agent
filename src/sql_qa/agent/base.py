import abc
from typing import Callable, List, Tuple, TypedDict, Optional, Union, Annotated
from langchain_core.runnables import Runnable
from langchain_core.tools import InjectedToolCallId, tool
from langchain_core.tools.base import BaseTool

from langgraph.graph import MessagesState
from langgraph.graph.graph import CompiledGraph
from langgraph.prebuilt import InjectedState
from langgraph.types import Command


class AgentBaseState(MessagesState):
    handoffs: Optional[List[str]]


class AgentBase(abc.ABC):
    def __init__(
        self,
        tools: List[Callable],
        handoffs: List[BaseTool],
        name: str,
    ) -> None:
        super().__init__()
        self._tools = tools
        self._handoffs = handoffs
        self._name = name
        self._handoff_nodes: List[BaseTool] = self._gen_internal_handoffs()
        self.graph = self._build_graph()

    @abc.abstractmethod
    def _build_graph(self) -> CompiledGraph:
        pass

    def _gen_internal_handoffs(self) -> List[BaseTool]:
        handoff_nodes: List[BaseTool] = []
        for ho in self._handoffs:

            @tool(ho.name, description=ho.description)
            def handoff_tool(
                state: Annotated[AgentBaseState, InjectedState],
                tool_call_id: Annotated[str, InjectedToolCallId],
            ) -> Command:
                tool_message = {
                    "role": "tool",
                    "content": f"Successfully transferred to {ho.name}",
                    "name": ho.name,
                    "tool_call_id": tool_call_id,
                }
                return Command(
                    goto=ho.name,
                    update={
                        "messages": state["messages"] + [tool_message],
                        "active_agent": ho.name,
                    },
                    graph=Command.PARENT,
                )

            handoff_nodes.append(handoff_tool)

        return handoff_nodes

    @property
    def handoff_nodes(self) -> Tuple[str, ...]:
        return tuple(n.name for n in self._handoff_nodes)
