"""Agent 封装 - 提供 .chat() 方法作为用户主要入口。"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import Any, Callable, Dict, List, Optional

from agentcore.adapters.decorators import _ToolWrapper, _SkillWrapper
from agentcore.adapters.skill import SkillBase
from agentcore.core.interfaces import LLMClient, MemoryInterface, ToolInterface
from agentcore.core.orchestrator import Orchestrator, StepRecord
from agentcore.core.tool_manager import ToolManager
from agentcore.runtime.broadcaster import Broadcaster
from agentcore.runtime.runner import SyncRunner
from agentcore.runtime.waiter import SyncWaiter
from agentcore.services.logger.file_logger import FileLogger
from agentcore.services.memory.sliding_window import SlidingWindowMemory


class Agent:
    """Agent 封装，提供友好的 .chat() 接口。"""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        memory: Optional[MemoryInterface] = None,
        system_prompt: Optional[str] = None,
        pool_size: int = 4,
        log_path: str = "",
    ):
        self._llm = llm
        self._memory = memory or SlidingWindowMemory()
        self._tool_manager = ToolManager()
        self._pool = ThreadPoolExecutor(max_workers=pool_size)
        self._waiter = SyncWaiter(pool=self._pool)
        self._broadcaster = Broadcaster(pool=self._pool)
        self._skills: Dict[str, _SkillWrapper] = {}
        self._system_prompt = system_prompt

        # 自动注册 JSONL 日志监听器
        if log_path:
            self._logger = FileLogger(log_path)
            self.add_listener("jsonl_logger", lambda record: self._logger.write(record))

    # --- 工具注册 ---

    def add_tool(self, tool: Any) -> None:
        """添加工具。接受 _ToolWrapper 或 ToolInterface 实例。"""
        if isinstance(tool, _ToolWrapper):
            self._tool_manager.register(tool)
        elif isinstance(tool, ToolInterface):
            self._tool_manager.register(tool)
        else:
            raise TypeError(f"不支持的工具类型: {type(tool)}")

    # --- 技能注册 ---

    def add_skill(self, skill: SkillBase) -> None:
        """添加技能。"""
        wrapper = _SkillWrapper(skill)
        self._skills[wrapper.name] = wrapper

    # --- 广播监听器 ---

    def add_listener(self, name: str, listener: Callable[[StepRecord], None]) -> None:
        """添加 StepRecord 监听器。"""
        self._broadcaster.register(name, listener)

    # --- 核心 chat 方法 ---

    def chat(
        self,
        user_input: str,
        session_id: str = "default",
        max_steps: int = 10,
        llm_timeout: float = 30.0,
        tool_timeout: float = 15.0,
        cancel_event: Optional[Event] = None,
        parent_skill_id: Optional[str] = None,
    ) -> str:
        """执行一次对话。

        返回最终结果字符串。内部创建 Orchestrator 实例并执行完整推理循环。
        """
        if not self._llm:
            raise ValueError("LLM 客户端未设置，请先通过 builder 或 setter 配置")

        # 检查技能触发
        skill_result = self._try_skill(user_input, parent_skill_id)
        if skill_result is not None:
            return skill_result

        # 生成 trace_id
        trace_id = uuid.uuid4().hex[:16]

        # 创建 Orchestrator 并执行
        orchestrator = Orchestrator(
            llm=self._llm,
            tool_manager=self._tool_manager,
            memory=self._memory,
            waiter=self._waiter,
            system_prompt=self._system_prompt,
        )
        runner = SyncRunner(orchestrator)
        result, steps = runner.run(
            user_input=user_input,
            session_id=session_id,
            max_steps=max_steps,
            llm_timeout=llm_timeout,
            tool_timeout=tool_timeout,
            cancel_event=cancel_event,
            parent_skill_id=parent_skill_id,
            trace_id=trace_id,
        )

        # 广播所有步骤
        for record in steps:
            self._broadcaster.publish(record)

        return result

    # --- 技能触发 ---

    def _try_skill(self, user_input: str, parent_skill_id: Optional[str] = None) -> Optional[str]:
        """检查用户输入是否匹配某个技能。匹配则执行并返回结果。"""
        for name, wrapper in self._skills.items():
            if name.lower() in user_input.lower():
                return wrapper.execute(self, user_input)
        return None

    # --- 生命周期 ---

    def shutdown(self) -> None:
        """释放资源。"""
        self._waiter.shutdown()
        self._pool.shutdown(wait=True)
