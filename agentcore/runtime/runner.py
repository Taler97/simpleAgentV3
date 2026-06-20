"""SyncRunner - 驱动生成器，管理 Orchestrator 生命周期。"""

from typing import Generator, List, Optional

from agentcore.core.orchestrator import Orchestrator, StepRecord


class SyncRunner:
    """同步运行器，驱动 Orchestrator 的生成器并收集所有 StepRecord。"""

    def __init__(self, orchestrator: Orchestrator):
        self._orchestrator = orchestrator

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
    ) -> tuple[str, List[StepRecord]]:
        """执行一次完整的 Agent 调用，返回 (最终结果, 步骤记录列表)."""
        steps: List[StepRecord] = []
        gen = self._orchestrator.run(
            user_input=user_input,
            session_id=session_id,
            max_steps=max_steps,
            llm_timeout=llm_timeout,
            tool_timeout=tool_timeout,
            cancel_event=cancel_event,
            parent_skill_id=parent_skill_id,
            trace_id=trace_id,
        )

        result = ""
        for record in gen:
            steps.append(record)
            result = record.result or record.observation or ""

        return result, steps
