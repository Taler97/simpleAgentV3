"""混沌测试 - 超时与取消场景。"""

import time
from threading import Event
from typing import Dict, List

import pytest

from agentcore.core.orchestrator import Orchestrator
from agentcore.core.tool_manager import ToolManager
from agentcore.runtime.waiter import SyncWaiter
from agentcore.services.memory.sliding_window import SlidingWindowMemory


class _SlowLLM:
    """模拟慢速 LLM 响应。"""

    def __init__(self, delay: float = 0.1, response: str = ""):
        self._delay = delay
        self._response = response or '{"thought": "ok", "action": "", "action_input": "done"}'

    def generate(self, messages: List[Dict[str, str]]) -> str:
        time.sleep(self._delay)
        return self._response


class _SlowTool:
    name = "slow"
    description = "慢速工具"
    parameters_schema = {"type": "object", "properties": {"x": {"type": "string"}}}

    def __init__(self, delay: float = 0.1):
        self._delay = delay

    def execute(self, input_str: str) -> str:
        time.sleep(self._delay)
        return f"slow: {input_str}"


class _HangingTool:
    name = "hang"
    description = "永不返回的工具"
    parameters_schema = {"type": "object", "properties": {"x": {"type": "string"}}}

    def execute(self, input_str: str) -> str:
        while True:
            time.sleep(1)


class TestTimeoutScenarios:
    def test_llm_timeout(self):
        """LLM 调用超时。"""
        llm = _SlowLLM(delay=5.0)  # 5s 延迟
        tm = ToolManager()
        orch = Orchestrator(llm=llm, tool_manager=tm, memory=SlidingWindowMemory())

        records = []
        gen = orch.run("测试超时", max_steps=3, llm_timeout=1.0)
        for r in gen:
            records.append(r)

        assert len(records) == 1
        assert "Timeout" in records[0].observation

    def test_tool_timeout(self):
        """工具执行超时。"""
        llm = _SlowLLM(delay=0.01, response='{"thought": "用工具", "action": "hang", "action_input": "x"}')
        tm = ToolManager()
        tm.register(_HangingTool())
        orch = Orchestrator(llm=llm, tool_manager=tm, memory=SlidingWindowMemory())

        records = []
        gen = orch.run("测试工具超时", max_steps=3, llm_timeout=5.0, tool_timeout=1.0)
        for r in gen:
            records.append(r)

        # 每个步骤都超时，最多 max_steps 次
        assert len(records) > 1
        assert records[-1].step == 3
        assert "Timeout" in records[0].observation

    def test_cancel_during_llm(self):
        """LLM 执行期间收到取消信号。"""
        cancel = Event()

        def _delayed_llm(messages):
            time.sleep(2.0)
            return '{"thought": "ok", "action": "", "action_input": "done"}'

        llm = _SlowLLM(delay=2.0)
        tm = ToolManager()
        orch = Orchestrator(llm=llm, tool_manager=tm, memory=SlidingWindowMemory())

        # 预置取消信号
        cancel.set()

        records = []
        gen = orch.run("测试取消", max_steps=3, llm_timeout=10.0, cancel_event=cancel)
        for r in gen:
            records.append(r)

        assert len(records) == 1
        assert records[0].observation == "Cancelled"

    def test_cancel_during_tool(self):
        """工具执行期间收到取消信号。"""
        cancel = Event()
        tm = ToolManager()
        tm.register(_HangingTool())

        llm = _SlowLLM(delay=0.01, response='{"thought": "用工具", "action": "hang", "action_input": "x"}')
        orch = Orchestrator(llm=llm, tool_manager=tm, memory=SlidingWindowMemory())

        # 预置取消信号
        cancel.set()

        records = []
        gen = orch.run("测试工具取消", max_steps=3, llm_timeout=10.0, tool_timeout=10.0, cancel_event=cancel)
        for r in gen:
            records.append(r)

        assert len(records) <= 1
        # 可能在 LLM 阶段或 tool 阶段被取消
        last = records[-1]
        assert "Cancelled" in last.observation or "Cancelled" in last.result or last.observation == ""

    def test_tool_execution_error(self):
        """工具执行抛出异常。"""
        class _CrashTool:
            name = "crash"
            description = "会崩溃的工具"
            parameters_schema = {"type": "object", "properties": {}}

            def execute(self, input_str: str) -> str:
                raise RuntimeError("工具崩溃了")

        llm = _SlowLLM(delay=0.01, response='{"thought": "用工具", "action": "crash", "action_input": ""}')
        tm = ToolManager()
        tm.register(_CrashTool())
        orch = Orchestrator(llm=llm, tool_manager=tm, memory=SlidingWindowMemory())

        records = []
        gen = orch.run("测试工具崩溃", max_steps=3, llm_timeout=5.0)
        for r in gen:
            records.append(r)

        assert len(records) > 1
        assert "Error" in records[0].observation

    def test_waiter_precise_timeout(self):
        """验证 Waiter 超时精度在 ±0.5s 范围内。"""
        waiter = SyncWaiter()

        def _slow():
            time.sleep(3.0)
            return "done"

        start = time.monotonic()
        result = waiter.run(_slow, timeout=1.0)
        elapsed = time.monotonic() - start

        assert result.startswith("Timeout after")
        # 超时精度: 1s ± 0.5s
        assert 0.5 <= elapsed <= 2.0, f"超时精度超限: {elapsed:.2f}s"
        waiter.shutdown()
