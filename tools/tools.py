"""内置工具集。"""

import ast
from datetime import datetime

from agentcore.adapters.decorators import tool


@tool
def calculator(expression: str) -> str:
    """计算数学表达式，支持 + - * / 和括号"""
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp,
                                      ast.Constant, ast.Add, ast.Sub,
                                      ast.Mult, ast.Div, ast.Pow)):
                return "错误: 不支持的表达式"
        return str(eval(compile(tree, "", "eval")))
    except Exception as e:
        return f"错误: {e}"


@tool
def now(format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前日期时间"""
    return datetime.now().strftime(format)


@tool
def echo(text: str) -> str:
    """返回输入的内容"""
    return text
