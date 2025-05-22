from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class InvokableBase(ABC):
    @abstractmethod
    def stream(self, *args: Any, **kwargs: Any) -> Any:
        return self.agent_executor.stream(*args, **kwargs)

    @abstractmethod
    def invoke(
        self,
        input: Dict[str, Any],
        *,
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        pass
