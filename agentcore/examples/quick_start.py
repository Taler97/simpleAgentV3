"""快速入门示例 - 展示 AgentCore V3 的基本用法。"""

from agentcore.adapters.agent import Agent
from agentcore.adapters.decorators import tool, skill
from agentcore.adapters.skill import SkillBase
from agentcore.services.llm.openai_sdk import OpenAILLM


# 1. 定义工具
@tool
def get_weather(city: str) -> str:
    """获取指定城市的天气"""
    return f"{city}: 25°C, 晴"

# 2. 定义技能


@skill
class WeatherForecastSkill(SkillBase):
    name = "weather_forecast"
    description = "获取多个城市的天气预报"

    def run(self, agent, user_input: str) -> str:
        # 提取城市列表（实际使用时建议用 LLM 提取）
        cities = user_input.replace("天气", "").replace("预报", "").split()
        results = []
        for city in cities:
            result = agent.chat(f"{city}天气怎么样？")
            results.append(result)
        return "\n".join(results)


# 3. 创建 Agent
agent = Agent(
    llm=OpenAILLM(model="gpt-4o", api_key="your-api-key"),
)
agent.add_tool(get_weather)
agent.add_skill(WeatherForecastSkill())

# 4. 执行对话
result = agent.chat("北京天气怎么样？")
print(result)

# 触发技能
result = agent.chat("weather_forecast 北京上海广州的天气")
print(result)
