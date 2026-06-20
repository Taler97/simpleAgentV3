"""装饰器 - @tool 和 @skill。"""

import inspect
import json
from functools import wraps
from typing import Any, Callable, Dict, get_type_hints

from agentcore.adapters.skill import SkillBase


class _ToolWrapper:
    """将函数包装为工具接口。"""

    def __init__(self, func: Callable):
        self._func = func
        self.name = func.__name__
        self.description = func.__doc__ or ""
        self.parameters_schema = self._build_schema()

    def _build_schema(self) -> Dict[str, Any]:
        sig = inspect.signature(self._func)
        hints = get_type_hints(self._func)
        properties = {}
        required = []

        for name, param in sig.parameters.items():
            if name == "self":
                continue
            param_type = hints.get(name, str)
            properties[name] = {
                "type": self._type_to_str(param_type),
                "description": f"参数 {name}",
            }
            if param.default is inspect.Parameter.empty:
                required.append(name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    @staticmethod
    def _type_to_str(tp: type) -> str:
        mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        return mapping.get(tp, "string")

    def execute(self, input_str: str) -> str:
        """执行包装的函数，自动将 JSON 字符串参数转换为关键字参数。"""
        try:
            kwargs = json.loads(input_str) if input_str.strip() else {}
        except json.JSONDecodeError:
            kwargs = {"input_str": input_str}

        result = self._func(**kwargs)
        return str(result)


class _SkillWrapper:
    """将 SkillBase 实例包装为可注册的技能描述。"""

    def __init__(self, skill_instance: SkillBase):
        self._skill = skill_instance
        self.name = skill_instance.name
        self.description = skill_instance.description

    def execute(self, agent: "Agent", user_input: str) -> str:  # noqa: F821
        return self._skill.run(agent, user_input)


def tool(func: Callable) -> _ToolWrapper:
    """@tool 装饰器：将函数注册为工具。

    读取函数签名生成 parameters_schema，注册到 ToolManager。
    """
    return _ToolWrapper(func)


def skill(cls: type) -> type:
    """@skill 装饰器：标记一个类为技能。

    该类需继承 SkillBase 并实现 run 方法。
    """
    if not issubclass(cls, SkillBase):
        raise TypeError(f"@skill 装饰器只能用于 SkillBase 的子类，收到: {cls}")
    return cls
