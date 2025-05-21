from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Literal, Optional, Sequence, Type, Union

from langchain_core.language_models import LanguageModelLike
from langchain_core.runnables.base import RunnableLike
from langchain_core.tools import BaseTool
from langchain_huggingface.llms.huggingface_pipeline import DEFAULT_BATCH_SIZE
from langgraph.prebuilt import ToolNode, create_react_agent
from langgraph.prebuilt.chat_agent_executor import (
    Prompt,
    StateSchemaType,
    StructuredResponseSchema,
)
from langgraph.store.base import BaseStore
from langgraph.types import Checkpointer
import tenacity

from sql_qa.llm.util import on_llm_retry_fail

from shared.logger import get_logger

logger = get_logger(__name__, log_file=f"./logs/{__name__}.log")


class BaseAdapter(ABC):
    @abstractmethod
    def __init__(
        self,
        model: Union[str, LanguageModelLike],
        tools: Union[Sequence[Union[BaseTool, Callable]], ToolNode],
        *,
        prompt: Optional[Prompt] = None,
        response_format: Optional[
            Union[StructuredResponseSchema, tuple[str, StructuredResponseSchema]]
        ] = None,
        pre_model_hook: Optional[RunnableLike] = None,
        state_schema: Optional[StateSchemaType] = None,
        config_schema: Optional[Type[Any]] = None,
        checkpointer: Optional[Checkpointer] = None,
        store: Optional[BaseStore] = None,
        interrupt_before: Optional[list[str]] = None,
        interrupt_after: Optional[list[str]] = None,
        debug: bool = False,
        version: Literal["v1", "v2"] = "v2",
        name: Optional[str] = None,
    ):
        self.model = model
        self.tools = tools
        self.prompt = prompt
        self.response_format = response_format
        self.pre_model_hook = pre_model_hook
        self.state_schema = state_schema
        self.config_schema = config_schema
        self.checkpointer = checkpointer
        self.store = store
        self.interrupt_before = interrupt_before
        self.interrupt_after = interrupt_after
        self.debug = debug
        self.version = version
        self.name = name

        self.agent_executor = None
        self._init_agent_executor()

    @abstractmethod
    def _init_agent_executor(self):
        pass

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


class ApiAdapter(BaseAdapter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _init_agent_executor(self):
        self.agent_executor = create_react_agent(
            model=self.model,
            tools=self.tools,
            prompt=self.prompt,
            response_format=self.response_format,
            pre_model_hook=self.pre_model_hook,
            state_schema=self.state_schema,
            config_schema=self.config_schema,
            checkpointer=self.checkpointer,
            store=self.store,
            interrupt_before=self.interrupt_before,
            interrupt_after=self.interrupt_after,
            debug=self.debug,
            version=self.version,
            name=self.name,
        )

    def stream(self, *args: Any, **kwargs: Any) -> Any:
        return self.agent_executor.stream(*args, **kwargs)

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(10),
        wait=tenacity.wait_exponential(multiplier=1, min=4, max=15),
        retry=tenacity.retry_if_exception_type(Exception),
        reraise=True,
        retry_error_callback=on_llm_retry_fail,
        before=lambda retry_state: (
            logger.warning(
                f"Retry attempt {retry_state.attempt_number} due to error: {retry_state.outcome.exception()}"
            )
            if retry_state.outcome
            else None
        ),
    )
    def invoke(self, *args, **kwargs: Any) -> Any:
        return self.agent_executor.invoke(*args, **kwargs)


class HuggingFaceAdapter(BaseAdapter):
    def __init__(
        self,
        task: str,
        backend: str = "default",
        device: Optional[int] = None,
        device_map: Optional[str] = None,
        model_kwargs: Optional[dict] = None,
        pipeline_kwargs: Optional[dict] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.pipeline_config = {
            "task": task,
            "backend": backend,
            "device": device,
            "device_map": device_map,
            "model_kwargs": model_kwargs,
            "pipeline_kwargs": pipeline_kwargs,
            "batch_size": batch_size,
        }

    def _init_agent_executor(self):
        from langchain_huggingface import ChatHuggingFace, HuggingFacePipeline

        llm = ChatHuggingFace(
            model_id=self.model,
            llm=HuggingFacePipeline.from_model_id(
                model_id=self.model,  # Explicitly pass the model ID string
                **self.pipeline_config,
            ),
        )
        self.agent_executor = create_react_agent(
            llm,
            tools=self.tools,
            prompt=self.prompt,
            checkpointer=self.checkpointer,
            store=self.store,
            interrupt_before=self.interrupt_before,
            interrupt_after=self.interrupt_after,
        )

    def stream(self, *args: Any, **kwargs: Any) -> Any:
        return self.agent_executor.stream(*args, **kwargs)

    def invoke(self, *args, **kwargs: Any) -> Any:
        return self.agent_executor.invoke(*args, **kwargs)
        pass
