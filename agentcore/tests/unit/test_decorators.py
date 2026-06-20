"""装饰器单元测试。"""

import pytest
from agentcore.adapters.decorators import tool, skill
from agentcore.adapters.skill import SkillBase


class TestToolDecorator:
    def test_wrapper_properties(self):
        @tool
        def get_weather(city: str) -> str:
            """获取天气"""
            return f"{city}: 25°C"

        assert get_weather.name == "get_weather"
        assert get_weather.description == "获取天气"
        assert "city" in get_weather.parameters_schema["properties"]
        assert get_weather.parameters_schema["required"] == ["city"]

    def test_execute_with_json(self):
        @tool
        def add(a: int, b: int) -> str:
            return str(a + b)

        result = add.execute('{"a": 1, "b": 2}')
        assert result == "3"

    def test_execute_no_args(self):
        @tool
        def hello() -> str:
            return "hi"

        result = hello.execute("")
        assert result == "hi"


class TestSkillDecorator:
    def test_skill_decorator_valid(self):
        @skill
        class MySkill(SkillBase):
            name = "my_skill"
            description = "我的技能"

            def run(self, agent, user_input: str) -> str:
                return f"processed: {user_input}"

        assert isinstance(MySkill, type)

    def test_skill_decorator_invalid(self):
        with pytest.raises(TypeError):
            @skill
            class NotASkill:
                pass
