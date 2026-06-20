"""ToolManager - 工具注册与原子执行。"""

from typing import Any, Dict

from agentcore.core.interfaces import ToolInterface


class ToolManager:
    """管理工具注册与执行。"""

    def __init__(self):
        self._tools: Dict[str, ToolInterface] = {}

    def register(self, tool: ToolInterface) -> None:
        """注册一个工具。"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolInterface:
        """根据名称获取工具。"""
        if name not in self._tools:
            raise KeyError(f"工具未找到: {name}")
        return self._tools[name]

    def execute(self, name: str, input_str: str) -> str:
        """执行指定名称的工具。"""
        return self.get(name).execute(input_str)

    def list_schemas(self) -> Dict[str, Any]:
        """返回所有工具的函数调用 schema（用于 LLM prompt 构建）。"""
        return {name: {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters_schema,
        } for name, tool in self._tools.items()}
