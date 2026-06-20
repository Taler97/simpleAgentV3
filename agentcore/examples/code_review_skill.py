"""CodeReviewSkill 示例 - 展示技能的多步骤编排能力。"""

from agentcore.adapters.decorators import skill
from agentcore.adapters.skill import SkillBase


@skill
class CodeReviewSkill(SkillBase):
    name = "code_review"
    description = "审查代码变更，生成审查报告"

    def run(self, agent, user_input: str) -> str:
        # 步骤 1: 提取 PR 信息
        pr_info = agent.chat(f"从以下输入中提取 PR/代码变更信息: {user_input}")

        # 步骤 2: 获取代码变更（模拟）
        diff = "模拟的代码变更内容..."

        # 步骤 3: 审查代码
        analysis = agent.chat(f"请审查以下代码变更:\n{diff}")

        # 步骤 4: 生成最终报告
        report = f"""## 代码审查报告

### PR 信息
{pr_info}

### 审查分析
{analysis}
"""
        return report
