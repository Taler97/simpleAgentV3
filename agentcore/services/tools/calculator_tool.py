"""计算器工具 - 执行数学表达式计算。"""

import ast
import operator
from agentcore.adapters.decorators import tool


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


def _eval_node(node) -> float:
    """安全地评估 AST 节点。"""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        op = _ALLOWED_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
        return op(_eval_node(node.left), _eval_node(node.right))
    elif isinstance(node, ast.UnaryOp):
        op = _ALLOWED_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
        return op(_eval_node(node.operand))
    else:
        raise ValueError(f"不支持的表达式类型: {type(node).__name__}")


@tool
def calculator(expression: str) -> str:
    """执行数学表达式计算，支持 + - * ** / %"""
    expr = expression.strip()
    if not expr:
        return "错误: 表达式为空"
    try:
        tree = ast.parse(expr, mode="eval")
        result = _eval_node(tree.body)
        return str(result)
    except Exception as e:
        return f"计算错误: {e}"
