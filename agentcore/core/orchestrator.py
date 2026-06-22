"""Orchestrator - 推理与工具调用循环引擎（ReAct 模式）。"""

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Generator, List, Optional

from agentcore.core.interfaces import LLMClient, MemoryInterface
from agentcore.core.parser import Parser
from agentcore.core.tool_manager import ToolManager
from agentcore.runtime.checkpointer import NullCheckpointer
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
    """构建工具描述的 prompt 片段（精简格式）。"""
    if not schemas:
        return "当前没有可用工具。"

    def _fmt_params(props: dict, required: list) -> str:
        parts = []
        for pname, pinfo in props.items():
            ptype = pinfo.get("type", "str")
            if pname in required:
                parts.append(f"{pname}: {ptype}")
            else:
                parts.append(f"[{pname}: {ptype}]")
        return ", ".join(parts)

    lines = []
    for name, schema in schemas.items():
        props = schema.get("parameters", {}).get("properties", {})
        req = schema.get("parameters", {}).get("required", [])
        params_str = _fmt_params(props, req)
        tool_line = f"### {name}({params_str})" if params_str else f"### {name}"
        lines.append(f"{tool_line}\n  {schema['description']}")
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
        checkpointer=None,
        max_parse_retries: int = 2,
        repeated_action_threshold: int = 3,
    ):
        self._llm = llm
        self._tool_manager = tool_manager
        self._memory = memory
        self._waiter = waiter or SyncWaiter()
        self._parser = parser or Parser()
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self._checkpointer = checkpointer or NullCheckpointer()
        self._max_parse_retries = max_parse_retries
        self._repeated_action_threshold = repeated_action_threshold

    # ── 公共辅助方法 ────────────────────────────────────

    @staticmethod
    def _detect_repeated_action(
        action: str,
        step_records: List[StepRecord],
        threshold: int = 3,
    ) -> bool:
        """检测最近 N 步是否存在重复的工具调用（陷入循环）。"""
        recent = [r for r in step_records[-threshold:] if r.action]
        if len(recent) < threshold:
            return False
        # 最近 threshold 次都是同一个工具
        actions = [r.action for r in recent[-threshold:]]
        return len(set(actions)) == 1 and actions[-1] == action

    def _save_ckpt(
        self,
        session_id: str,
        step: int,
        messages: List[Dict[str, str]],
        step_records: List[StepRecord],
        user_input: str,
        max_steps: int,
        trace_id: str,
        parent_skill_id: Optional[str],
        status: str,
        result: str = "",
    ) -> None:
        """写检查点。"""
        self._checkpointer.save(session_id, {
            "step": step,
            "messages": messages,
            "step_records": [r.to_dict() for r in step_records],
            "user_input": user_input,
            "max_steps": max_steps,
            "trace_id": trace_id,
            "parent_skill_id": parent_skill_id,
            "status": status,
            "result": result,
        })

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

        # ── 检查点恢复 ──────────────────────────────────
        step_records: List[StepRecord] = []
        start_step = 1
        ckpt = self._checkpointer.load(session_id)
        if ckpt and ckpt.get("status") == "in_progress":
            # 恢复 messages 和步骤记录
            messages = ckpt["messages"]
            start_step = ckpt["step"] + 1
            for sd in ckpt.get("step_records", []):
                step_records.append(StepRecord(**sd))
            # 覆盖原始参数，确保恢复后续流程一致
            trace_id = ckpt.get("trace_id", trace_id)
            parent_skill_id = ckpt.get("parent_skill_id", parent_skill_id)
            user_input = ckpt.get("user_input", user_input)
            max_steps = ckpt.get("max_steps", max_steps)
            # 重新生成 _record 闭包以使用更新后的变量
            def _record(**kw):
                return StepRecord(trace_id=trace_id, session_id=session_id, **kw)
        elif ckpt and ckpt.get("status") == "completed":
            # 已完成不缓存，删掉走正常流程
            self._checkpointer.delete(session_id)

        parse_retry_count = 0

        for step in range(start_step, max_steps + 1):
            # === 步骤 1: 调用 LLM ===
            llm_result = self._waiter.run(
                func=lambda: self._llm.generate(
                    messages,
                    response_format={"type": "json_object"},
                ),
                timeout=llm_timeout,
                cancel_event=cancel_event,
            )

            if llm_result.startswith("Cancelled") or llm_result.startswith("Timeout"):
                record = _record(
                    step=step, action="", action_input="",
                    thought="", observation=llm_result, result=llm_result,
                )
                step_records.append(record)
                yield record
                return llm_result

            if llm_result.startswith("Error:"):
                record = _record(
                    step=step, action="", action_input="",
                    thought="", observation=llm_result, result=llm_result,
                )
                step_records.append(record)
                yield record
                return llm_result

            # === 步骤 2: 解析 LLM 响应 ===
            try:
                parsed = self._parser.parse(llm_result)
            except ValueError as e:
                if parse_retry_count < self._max_parse_retries:
                    parse_retry_count += 1
                    error_msg = (
                        f"JSON 格式错误，请严格按照 {{\\\"thought\\\": ..., \\\"action\\\": ..., \\\"action_input\\\": ...}} "
                        f"格式输出有效的 JSON，且只输出 JSON。错误: {e}"
                    )
                    messages.append({"role": "user", "content": error_msg})
                    continue
                error_msg = f"多次解析失败 (已重试 {self._max_parse_retries} 次): {e}"
                record = _record(
                    step=step, action="", action_input="", thought="",
                    observation=error_msg, result=error_msg,
                )
                step_records.append(record)
                yield record
                return error_msg

            thought = parsed.get("thought", "")
            action = parsed.get("action", "")
            action_input = parsed.get("action_input", "")

            # === 步骤 3: 检查是否为最终答案 ===
            if not action:
                if not action_input.strip():
                    error_msg = "action_input 不能为空，请将你的回答填写在 action_input 字段中"
                    messages.append({"role": "user", "content": error_msg})
                    continue
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
                step_records.append(record)
                yield record
                # 清理检查点（已完成不再需要缓存）
                self._checkpointer.delete(session_id)
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
            step_records.append(record)
            yield record

            # === 步骤 5: 将工具结果加入消息作为观察 ===
            messages.append({"role": "assistant", "content": llm_result})
            messages.append({"role": "user", "content": f"观察结果: {tool_result}"})

            # === 步骤 6: 循环检测 ─────────────────────────
            if self._detect_repeated_action(
                action, step_records, self._repeated_action_threshold,
            ):
                messages.append({
                    "role": "user",
                    "content": (
                        f"你已连续多次调用 \"{action}\"，未能取得有效进展。"
                        "请尝试换一种方式，或直接基于已有信息给出最终答案。"
                    ),
                })

            # ── 写进行中的检查点 ─────────────────────────
            self._save_ckpt(
                session_id, step, messages, step_records,
                user_input, max_steps, trace_id, parent_skill_id,
                status="in_progress",
            )

        # 超过 max_steps
        timeout_msg = f"已达到最大步骤数 ({max_steps})，停止执行"
        record = _record(
            step=max_steps, action="", action_input="",
            thought="", observation=timeout_msg, result=timeout_msg,
        )
        step_records.append(record)
        yield record
        # 超时也保存完成状态（失败的完成）
        self._save_ckpt(
            session_id, max_steps, messages, step_records,
            user_input, max_steps, trace_id, parent_skill_id,
            status="completed", result=timeout_msg,
        )
        return timeout_msg
