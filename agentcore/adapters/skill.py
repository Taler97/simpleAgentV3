"""SkillBase 基类 - 技能是宏观流程编排器，可多次调用 agent.chat()。"""

from abc import ABC, abstractmethod
from typing import Optional


class SkillBase(ABC):
    """技能基类。继承此类并实现 run 方法。"""

    name: str = ""
    description: str = ""

    def __init__(self):
        if not self.name:
            self.name = self.__class__.__name__
        if not self.description:
            self.description = self.__class__.__doc__ or ""

    @abstractmethod
    def run(self, agent: "Agent", user_input: str) -> str:  # noqa: F821
        """执行技能。可多次调用 agent.chat()。"""
        ...
