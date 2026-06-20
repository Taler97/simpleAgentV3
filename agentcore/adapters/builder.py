"""AgentBuilder - YAML 配置驱动，显式组装 Agent。"""

from typing import Any, Dict, Optional

import yaml

from agentcore.adapters.agent import Agent
from agentcore.services.memory.sliding_window import SlidingWindowMemory


class AgentBuilder:
    """从 YAML 配置构建 Agent 实例。显式组装，非黑盒发现。"""

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._llm = None
        self._memory = None
        self._system_prompt = None
        self._pool_size = 4

    @classmethod
    def from_yaml(cls, path: str) -> "AgentBuilder":
        """读取 YAML 配置文件。"""
        builder = cls()
        with open(path, "r", encoding="utf-8") as f:
            builder._config = yaml.safe_load(f)
        return builder

    def build(self) -> Agent:
        """根据配置构建 Agent。"""
        config = self._config or {}

        # LLM 配置（延迟导入，openai 为可选依赖）
        from agentcore.services.llm.openai_sdk import OpenAILLM

        llm_config = config.get("llm", {})
        llm = OpenAILLM(
            model=llm_config.get("model", "gpt-4o"),
            api_key=llm_config.get("api_key", ""),
            base_url=llm_config.get("base_url", ""),
            temperature=llm_config.get("temperature", 0.7),
            max_tokens=llm_config.get("max_tokens", 4096),
        )

        # Memory 配置
        memory_config = config.get("memory", {})
        memory = SlidingWindowMemory(
            window_size=memory_config.get("window_size", 10),
        )

        # Runtime 配置
        runtime_config = config.get("runtime", {})
        pool_size = runtime_config.get("pool_size", 4)

        # System prompt
        system_prompt = config.get("system_prompt", None)

        agent = Agent(
            llm=llm,
            memory=memory,
            system_prompt=system_prompt,
            pool_size=pool_size,
        )

        # 注册内置工具
        self._register_builtin_tools(agent)

        return agent

    def _register_builtin_tools(self, agent: Agent) -> None:
        """注册内置工具。"""
        from agentcore.services.tools.datetime_tool import DatetimeTool
        from agentcore.services.tools.calculator_tool import CalculatorTool

        agent.add_tool(DatetimeTool())
        agent.add_tool(CalculatorTool())
