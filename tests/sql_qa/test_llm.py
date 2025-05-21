import pytest
from unittest.mock import MagicMock, patch
from typing import Any, Dict, List

from langchain_core.language_models import LanguageModelLike
from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.chat_agent_executor import Prompt, StructuredResponseSchema

from sql_qa.llm.adapter import ApiAdapter, HuggingFaceAdapter
from sql_qa.llm.type import LLMInput


@pytest.fixture
def mock_model():
    return MagicMock(spec=LanguageModelLike)


@pytest.fixture
def mock_tools():
    return [MagicMock(spec=BaseTool)]


@pytest.fixture
def mock_prompt():
    return MagicMock(spec=Prompt)


@pytest.fixture
def mock_response_format():
    return MagicMock(spec=StructuredResponseSchema)


@pytest.fixture
def mock_agent_executor():
    executor = MagicMock()
    executor.stream.return_value = iter(["test response"])
    executor.invoke.return_value = {"response": "test response"}
    return executor


class TestLLMApiAdapter:
    def test_init(self, mock_model, mock_tools):
        adapter = ApiAdapter(
            model=mock_model, tools=mock_tools, debug=True, version="v2"
        )

        assert adapter.model == mock_model
        assert adapter.tools == mock_tools
        assert adapter.debug is True
        assert adapter.version == "v2"

    @patch("sql_qa.llm.adapter.create_react_agent")
    def test_init_agent_executor(
        self, mock_create_agent, mock_model, mock_tools, mock_agent_executor
    ):
        mock_create_agent.return_value = mock_agent_executor

        adapter = ApiAdapter(model=mock_model, tools=mock_tools)

        mock_create_agent.assert_called_once()
        assert adapter.agent_executor == mock_agent_executor

    def test_stream(self, mock_model, mock_tools, mock_agent_executor):
        adapter = ApiAdapter(model=mock_model, tools=mock_tools)
        adapter.agent_executor = mock_agent_executor

        input_data: Dict[str, Any] = {"query": "test query"}
        result = list(adapter.stream(**input_data))

        assert result == ["test response"]
        mock_agent_executor.stream.assert_called_once_with(**input_data)


class TestLLMHuggingFaceAdapter:
    def test_init(self, mock_model, mock_tools):
        adapter = HuggingFaceAdapter(
            model=mock_model,
            tools=mock_tools,
            task="text-generation",
            device_map="auto",
        )

        assert adapter.model == mock_model
        assert adapter.tools == mock_tools
        assert adapter.pipeline_config["task"] == "text-generation"
        assert adapter.pipeline_config["device_map"] == "auto"

    @patch("sql_qa.llm.adapter.create_react_agent")
    @patch("sql_qa.llm.adapter.ChatHuggingFace")
    @patch("sql_qa.llm.adapter.HuggingFacePipeline")
    def test_init_agent_executor(
        self,
        mock_hf_pipeline,
        mock_chat_hf,
        mock_create_agent,
        mock_model,
        mock_tools,
        mock_agent_executor,
    ):
        mock_chat_hf.return_value = MagicMock()
        mock_create_agent.return_value = mock_agent_executor

        adapter = HuggingFaceAdapter(
            model=mock_model, tools=mock_tools, task="text-generation"
        )

        mock_hf_pipeline.from_model_id.assert_called_once()
        mock_chat_hf.assert_called_once()
        mock_create_agent.assert_called_once()
        assert adapter.agent_executor == mock_agent_executor

    def test_stream(self, mock_model, mock_tools, mock_agent_executor):
        adapter = HuggingFaceAdapter(
            model=mock_model, tools=mock_tools, task="text-generation"
        )
        adapter.agent_executor = mock_agent_executor

        input_data: Dict[str, Any] = {"query": "test query"}
        result = list(adapter.stream(**input_data))

        assert result == ["test response"]
        mock_agent_executor.stream.assert_called_once_with(**input_data)
