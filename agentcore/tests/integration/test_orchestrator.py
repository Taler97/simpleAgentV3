"""集成测试 - 使用 mock LLM 测试完整 ReAct 循环。"""

from typing import Any, Dict, List, Optional
from unittest.mock import Mock

import pytest

from agentcore.core.interfaces import LLMClient
from agentcore.core.orchestrator import Orchestrator
from agentcore.core.parser import Parser
from agentcore.core.tool_manager import ToolManager
from agentcore.runtime.waiter import SyncWaiter
from agentcore.services.memory.sliding_window import SlidingWindowMemory


class MockLLM:
    """可控的 mock LLM，按顺序返回预设响应。"""

    def __init__(self, responses: List[str]):
        self._responses = list(responses)
        self.call_count = 0
        self.last_messages = None

    def generate(self, messages: List[Dict[str, str]]) -> str:
        self.call_count += 1
        self.last_messages = messages
        if not self._responses:
            raise RuntimeError("MockLLM: 没有更多预设响应")
        return self._responses.pop(0)


class _EchoTool:
    name = "echo"
    description = "返回输入内容"
    parameters_schema = {"type": "object", "properties": {"text": {"type": "string"}}}

    def execute(self, input_str: str) -> str:
        return f"echo: {input_str}"


class _AddTool:
    name = "add"
    description = "两数相加"
    parameters_schema = {
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
    }

    def execute(self, input_str: str) -> str:
        return "3"


@pytest.fixture
def orchestrator():
    llm = MockLLM([])
    tm = ToolManager()
    tm.register(_EchoTool())
    return Orchestrator(llm=llm, tool_manager=tm, memory=SlidingWindowMemory())


class TestOrchestratorIntegration:
    def test_single_step_answer(self):
        """单步直接返回最终答案。"""
        llm = MockLLM(['{"thought": "直接回答", "action": "", "action_input": "你好"}'])
        tm = ToolManager()
        orch = Orchestrator(llm=llm, tool_manager=tm, memory=SlidingWindowMemory())

        records = []
        gen = orch.run("你好", max_steps=5)
        for r in gen:
            records.append(r)

        assert len(records) == 1
        assert records[0].result == "你好"
        assert records[0].action == ""
        assert llm.call_count == 1

    def test_multi_step_tool_call(self):
        """多步：调用工具后返回最终答案。"""
        llm = MockLLM([
            '{"thought": "需要计算", "action": "echo", "action_input": "{\\"text\\": \\"hello\\"}"}',
            '{"thought": "已完成", "action": "", "action_input": "结果是 hello"}',
        ])
        tm = ToolManager()
        tm.register(_EchoTool())
        orch = Orchestrator(llm=llm, tool_manager=tm, memory=SlidingWindowMemory())

        records = []
        gen = orch.run("测试", max_steps=5)
        for r in gen:
            records.append(r)

        assert len(records) == 2
        assert records[0].action == "echo"
        assert records[0].observation == "echo: {\"text\": \"hello\"}"
        assert records[1].result == "结果是 hello"
        assert llm.call_count == 2

    def test_max_steps_reached(self):
        """超过最大步骤数限制。"""
        llm = MockLLM([
            '{"thought": "继续", "action": "echo", "action_input": "x"}',
            '{"thought": "继续", "action": "echo", "action_input": "x"}',
        ])
        tm = ToolManager()
        tm.register(_EchoTool())
        orch = Orchestrator(llm=llm, tool_manager=tm, memory=SlidingWindowMemory())

        records = []
        gen = orch.run("测试", max_steps=2)
        for r in gen:
            records.append(r)

        # 2 次 tool 调用 + 1 次 max_steps 终止
        assert len(records) == 3
        assert "最大步骤数" in records[-1].observation

    def test_tool_not_found(self):
        """工具不存在。"""
        llm = MockLLM([
            '{"thought": "用未知工具", "action": "nonexistent", "action_input": "x"}',
        ])
        tm = ToolManager()
        orch = Orchestrator(llm=llm, tool_manager=tm, memory=SlidingWindowMemory())

        records = []
        gen = orch.run("测试", max_steps=5)
        for r in gen:
            records.append(r)

        # 第1步: 工具未找到 → Error; 第2步: LLM 无更多响应 → Error
        assert len(records) == 2
        assert "Error" in records[0].observation

    def test_llm_returns_invalid_json(self):
        """LLM 返回无效 JSON。"""
        llm = MockLLM(["这不是 JSON"])
        tm = ToolManager()
        orch = Orchestrator(llm=llm, tool_manager=tm, memory=SlidingWindowMemory())

        records = []
        gen = orch.run("测试", max_steps=5)
        for r in gen:
            records.append(r)

        assert len(records) == 1
        assert "解析失败" in records[0].observation

    def test_trace_id_passthrough(self):
        """trace_id 透传到所有 StepRecord。"""
        llm = MockLLM([
            '{"thought": "step1", "action": "echo", "action_input": "a"}',
            '{"thought": "step2", "action": "", "action_input": "done"}',
        ])
        tm = ToolManager()
        tm.register(_EchoTool())
        orch = Orchestrator(llm=llm, tool_manager=tm, memory=SlidingWindowMemory())

        records = []
        gen = orch.run("test", max_steps=5, trace_id="test-trace-123")
        for r in gen:
            records.append(r)

        assert len(records) == 2
        for r in records:
            assert r.trace_id == "test-trace-123"

    def test_parser_cleanup_restores_original(self):
        """Parser 执行清理后原始功能不受影响。"""
        import json

        raw = '{"thought": "test", "action": "calc",}'
        result = Parser.parse(raw)
        # 清理后能正常解析带尾部逗号的 JSON
        assert result["thought"] == "test"
        assert result["action"] == "calc"

        # 验证 Parser 仍然是可复用的
        result2 = Parser.parse('{"thought": "ok", "action": ""}')
        assert result2["thought"] == "ok"
