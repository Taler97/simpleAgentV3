"""Orchestrator - 推理与工具调用循环引擎（ReAct 模式）。"""

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Generator, List, Optional

from agentcore.core.interfaces import LLMClient, MemoryInterface
from agentcore.core.parser import Parser
from agentcore.core.tool_manager import ToolManager
from agentcore.runtime.waiter import SyncWaiter


@dataclass
class StepRecord:
    """单步执行的完整记录。"""
    step: int
    action: str  # 工具名称或空字符串（最终答案）
    action_input: str
    thought: str
    trace_id: str = ""  # 调用链路追踪 ID
    session_id: str = "default"
    observation: str = ""
    result: str = ""
    llm_latency: float = 0.0
    tool_latency: float = 0.0
    parent_skill_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# 默认系统 Prompt
DEFAULT_SYSTEM_PROMPT = """你是一个有帮助的 AI 助手。你可以使用以下工具：

{tools_section}

请以 JSON 格式回复，包含以下字段：
- "thought": 你的思考过程
- "action": 要使用的工具名称，如果不需要工具则为 ""（空字符串）
- "action_input": 工具的输入参数（JSON 字符串），如果不需要工具则为 ""

注意：如果你的回复是最终答案，请将 action 设为 "" 并将答案放在 action_input 中。"""


def _build_tools_section(schemas: Dict[str, Any]) -> str:
    """构建工具描述的 prompt 片段。"""
    if not schemas:
        return "当前没有可用工具。"

    lines = []
    for name, schema in schemas.items():
        params = json.dumps(schema.get("parameters", {}), ensure_ascii=False, indent=2)
        lines.append(f"### {name}\n描述: {schema['description']}\n参数:\n{params}")
    return "\n\n".join(lines)


class Orchestrator:
    """ReAct 推理循环引擎。"""

    def __init__(
        self,
        llm: LLMClient,
        tool_manager: ToolManager,
        memory: MemoryInterface,
        waiter: Optional[SyncWaiter] = None,
        parser: Optional[Parser] = None,
        system_prompt: Optional[str] = None,
    ):
        self._llm = llm
        self._tool_manager = tool_manager
        self._memory = memory
        self._waiter = waiter or SyncWaiter()
        self._parser = parser or Parser()
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    def run(
        self,
        user_input: str,
        session_id: str = "default",
        max_steps: int = 10,
        llm_timeout: float = 30.0,
        tool_timeout: float = 15.0,
        cancel_event=None,
        parent_skill_id: Optional[str] = None,
        trace_id: str = "",
    ) -> Generator[StepRecord, None, str]:
        """执行 ReAct 循环，逐步产生 StepRecord，最终返回结果字符串。"""
        # 获取历史记忆
        history = self._memory.get_context(session_id)

        # 构建 tools section
        schemas = self._tool_manager.list_schemas()
        tools_section = _build_tools_section(schemas)

        # 初始化消息列表
        messages = [
            {"role": "system", "content": self._system_prompt.format(tools_section=tools_section)},
            *history,
            {"role": "user", "content": user_input},
        ]

        def _record(**kw):
            return StepRecord(trace_id=trace_id, session_id=session_id, **kw)

        for step in range(1, max_steps + 1):
            # === 步骤 1: 调用 LLM ===
            llm_result = self._waiter.run(
                func=lambda: self._llm.generate(messages),
                timeout=llm_timeout,
                cancel_event=cancel_event,
            )

            if llm_result.startswith("Cancelled") or llm_result.startswith("Timeout"):
                record = _record(
                    step=step, action="", action_input="",
                    thought="", observation=llm_result, result=llm_result,
                )
                yield record
                return llm_result

            if llm_result.startswith("Error:"):
                record = _record(
                    step=step, action="", action_input="",
                    thought="", observation=llm_result, result=llm_result,
                )
                yield record
                return llm_result

            # === 步骤 2: 解析 LLM 响应 ===
            try:
                parsed = self._parser.parse(llm_result)
            except ValueError as e:
                error_msg = f"解析失败: {e}"
                record = _record(
                    step=step, action="", action_input="", thought="",
                    observation=error_msg, result=error_msg,
                )
                yield record
                return error_msg

            thought = parsed.get("thought", "")
            action = parsed.get("action", "")
            action_input = parsed.get("action_input", "")

            # === 步骤 3: 检查是否为最终答案 ===
            if not action:
                # 保存到记忆
                self._memory.save({
                    "role": "user",
                    "content": user_input,
                    "session_id": session_id,
                })
                self._memory.save({
                    "role": "assistant",
                    "content": action_input,
                    "session_id": session_id,
                })
                record = _record(
                    step=step, action="", action_input="",
                    thought=thought, result=action_input,
                    parent_skill_id=parent_skill_id,
                )
                yield record
                return action_input

            # === 步骤 4: 执行工具 ===
            tool_result = self._waiter.run(
                func=lambda: self._tool_manager.execute(action, action_input),
                timeout=tool_timeout,
                cancel_event=cancel_event,
            )

            record = _record(
                step=step, action=action, action_input=action_input,
                thought=thought, observation=tool_result,
                parent_skill_id=parent_skill_id,
            )
            yield record

            # === 步骤 5: 将工具结果加入消息作为观察 ===
            messages.append({"role": "assistant", "content": llm_result})
            messages.append({"role": "user", "content": f"观察结果: {tool_result}"})

        # 超过 max_steps
        timeout_msg = f"已达到最大步骤数 ({max_steps})，停止执行"
        record = _record(
            step=max_steps, action="", action_input="",
            thought="", observation=timeout_msg, result=timeout_msg,
        )
        yield record
        return timeout_msg
