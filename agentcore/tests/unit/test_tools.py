"""内置工具单元测试。"""

from agentcore.services.tools.datetime_tool import DatetimeTool
from agentcore.services.tools.calculator_tool import CalculatorTool


class TestCalculatorTool:
    def test_addition(self):
        tool = CalculatorTool()
        result = tool.execute("1 + 2")
        assert result == "3"

    def test_complex_expression(self):
        tool = CalculatorTool()
        result = tool.execute("(1 + 2) * 3 - 4 / 2")
        assert float(result) == 7.0

    def test_power(self):
        tool = CalculatorTool()
        result = tool.execute("2 ** 10")
        assert result == "1024"

    def test_empty_input(self):
        tool = CalculatorTool()
        result = tool.execute("")
        assert "错误" in result

    def test_invalid_expression(self):
        tool = CalculatorTool()
        result = tool.execute("1 + abc")
        assert "错误" in result


class TestDatetimeTool:
    def test_default_format(self):
        tool = DatetimeTool()
        result = tool.execute("")
        assert len(result) == 19  # %Y-%m-%d %H:%M:%S

    def test_custom_format(self):
        tool = DatetimeTool()
        result = tool.execute("%Y")
        assert len(result) == 4
        assert result.isdigit()
