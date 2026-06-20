"""ToolManager 单元测试。"""

import pytest
from agentcore.core.tool_manager import ToolManager


class _FakeTool:
    name = "test_tool"
    description = "测试工具"
    parameters_schema = {"type": "object", "properties": {}}

    def execute(self, input_str: str) -> str:
        return f"executed: {input_str}"


class TestToolManager:
    def test_register_and_get(self):
        mgr = ToolManager()
        tool = _FakeTool()
        mgr.register(tool)
        assert mgr.get("test_tool") is tool

    def test_get_not_found(self):
        mgr = ToolManager()
        with pytest.raises(KeyError):
            mgr.get("nonexistent")

    def test_execute(self):
        mgr = ToolManager()
        mgr.register(_FakeTool())
        result = mgr.execute("test_tool", "hello")
        assert result == "executed: hello"

    def test_list_schemas(self):
        mgr = ToolManager()
        mgr.register(_FakeTool())
        schemas = mgr.list_schemas()
        assert "test_tool" in schemas
        assert schemas["test_tool"]["description"] == "测试工具"
