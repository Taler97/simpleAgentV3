"""内置工具单元测试。"""

from agentcore.services.tools.datetime_tool import datetime as datetime_fn
from agentcore.services.tools.calculator_tool import calculator


class TestCalculatorTool:
    def test_addition(self):
        result = calculator.execute('{"expression": "1 + 2"}')
        assert result == "3"

    def test_complex_expression(self):
        result = calculator.execute('{"expression": "(1 + 2) * 3 - 4 / 2"}')
        assert float(result) == 7.0

    def test_power(self):
        result = calculator.execute('{"expression": "2 ** 10"}')
        assert result == "1024"

    def test_empty_input(self):
        result = calculator.execute('{"expression": ""}')
        assert "错误" in result

    def test_invalid_expression(self):
        result = calculator.execute('{"expression": "1 + abc"}')
        assert "错误" in result


class TestDatetimeTool:
    def test_default_format(self):
        result = datetime_fn.execute("")
        assert len(result) == 19  # %Y-%m-%d %H:%M:%S

    def test_custom_format(self):
        result = datetime_fn.execute('{"format": "%Y"}')
        assert len(result) == 4
        assert result.isdigit()
