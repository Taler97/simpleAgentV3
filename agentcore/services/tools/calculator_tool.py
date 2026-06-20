"""计算器工具 - 执行数学表达式计算。"""

import ast
import operator
from typing import Any, Dict


# 安全运算白名单
_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


class CalculatorTool:
    name = "calculator"
    description = "执行数学表达式计算，支持 + - * / ** %"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "数学表达式，如 1 + 2 * 3",
            }
        },
        "required": ["expression"],
    }

    def execute(self, input_str: str) -> str:
        """安全执行数学表达式。"""
        expr = input_str.strip()
        if not expr:
            return "错误: 表达式为空"
        try:
            tree = ast.parse(expr, mode="eval")
            result = self._eval(tree.body)
            return str(result)
        except Exception as e:
            return f"计算错误: {e}"

    def _eval(self, node) -> float:
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            op = _ALLOWED_OPS.get(type(node.op))
            if op is None:
                raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
            return op(self._eval(node.left), self._eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            op = _ALLOWED_OPS.get(type(node.op))
            if op is None:
                raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
            return op(self._eval(node.operand))
        else:
            raise ValueError(f"不支持的表达式类型: {type(node).__name__}")
