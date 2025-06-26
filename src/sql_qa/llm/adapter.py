from abc import ABC, abstractmethod
from typing import (
    Any,
    Callable,
    Dict,
    Literal,
    Optional,
    Sequence,
    Type,
    Union,
    TypeVar,
    cast,
)

from langgraph.graph.graph import CompiledGraph
from langchain_core.language_models import BaseChatModel, LanguageModelLike
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

from sql_qa.llm.base import InvokableBase
from sql_qa.llm.util import on_llm_retry_fail

from shared.logger import logger


API_MODELS = ["gemini", "openai", "anthropic", "mistral"]


class BaseAdapter(InvokableBase, ABC):
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
        stop=tenacity.stop_after_attempt(7),
        wait=tenacity.wait_exponential(multiplier=1, min=7, max=60),
        retry=tenacity.retry_if_exception_type(Exception),
        reraise=True,
        retry_error_callback=on_llm_retry_fail,
        before_sleep=lambda retry_state: (
            logger.warning(
                f"Retry attempt {retry_state.attempt_number} due to error: {retry_state.outcome.exception()}"
            )
            if retry_state.outcome
            else logger.warning(
                f"Retry attempt {retry_state.attempt_number} due to unknown error"
            )
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


_retry_wrapper = tenacity.retry(
    stop=tenacity.stop_after_attempt(1),
    wait=tenacity.wait_exponential(multiplier=1, min=7, max=60),
    retry=tenacity.retry_if_exception_type(Exception),
    reraise=True,
    retry_error_callback=on_llm_retry_fail,
    before_sleep=lambda retry_state: (
        logger.warning(
            f"Retry attempt {retry_state.attempt_number} due to error: {retry_state.outcome.exception()}"
        )
        if retry_state.outcome
        else logger.warning(
            f"Retry attempt {retry_state.attempt_number} due to unknown error"
        )
    ),
)


def get_react_agent(
    model: Union[str, LanguageModelLike],
    tools: Union[Sequence[Union[BaseTool, Callable]], ToolNode] = [],
    *,
    prompt: Optional[Prompt] = None,
    response_format: Optional[
        Union[
            StructuredResponseSchema,
            tuple[str, StructuredResponseSchema],
            Dict[Any, Any],
        ]
    ] = None,
    pre_model_hook: Optional[RunnableLike] = None,
    post_model_hook: Optional[RunnableLike] = None,
    state_schema: Optional[StateSchemaType] = None,
    config_schema: Optional[Type[Any]] = None,
    checkpointer: Optional[Checkpointer] = None,
    store: Optional[BaseStore] = None,
    interrupt_before: Optional[list[str]] = None,
    interrupt_after: Optional[list[str]] = None,
    debug: bool = False,
    version: Literal["v1", "v2"] = "v2",
    name: Optional[str] = None,
) -> CompiledGraph:
    agent_executor: CompiledGraph
    if type(model) == str and not [m for m in API_MODELS if m in model]:
        # HuggingFace model
        # TODO: HF model config
        pipeline_config = {
            # "task": task,
            # "backend": backend,
            # "device": device,
            # "device_map": device_map,
            # "model_kwargs": model_kwargs,
            # "pipeline_kwargs": pipeline_kwargs,
            # "batch_size": batch_size,
        }

        from langchain_huggingface import ChatHuggingFace, HuggingFacePipeline

        llm = ChatHuggingFace(
            model_id=model,
            llm=HuggingFacePipeline.from_model_id(
                model_id=model,  # Explicitly pass the model ID string
                **pipeline_config,
            ),
        )
        agent_executor = create_react_agent(
            llm,
            tools=tools,
            post_model_hook=post_model_hook,
            prompt=prompt,
            checkpointer=checkpointer,
            store=store,
            interrupt_before=interrupt_before,
            interrupt_after=interrupt_after,
        )
    else:
        agent_executor = create_react_agent(
            model,
            tools,
            prompt=prompt,
            response_format=response_format,
            pre_model_hook=pre_model_hook,
            post_model_hook=post_model_hook,
            state_schema=state_schema,
            config_schema=config_schema,
            checkpointer=checkpointer,
            store=store,
            interrupt_before=interrupt_before,
            interrupt_after=interrupt_after,
            debug=debug,
            version=version,
            name=name,
        )

    agent_executor.invoke = _retry_wrapper(agent_executor.invoke)
    agent_executor.stream = _retry_wrapper(agent_executor.stream)
    agent_executor.ainvoke = _retry_wrapper(agent_executor.ainvoke)
    return agent_executor


def get_chat_model_init(
    model: Optional[str] = None,
    *,
    model_provider: Optional[str] = None,
    configurable_fields: Optional[
        Union[Literal["any"], list[str], tuple[str, ...]]
    ] = None,
    config_prefix: Optional[str] = None,
    **kwargs: Any,
) -> BaseChatModel:
    from langchain.chat_models import init_chat_model

    return cast(
        BaseChatModel,
        init_chat_model(
            model=model,
            model_provider=model_provider,
            configurable_fields=configurable_fields,
            config_prefix=config_prefix,
            **kwargs,
        ),
    )
