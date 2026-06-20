"""
AgentCore V3 — 像 SpringBoot 一样启动你的 AI Agent.

用法:
    python main.py                          # 交互式对话
    python main.py "1+1等于几？"             # 单次提问
    python main.py --help                    # 查看帮助

配置优先级: YAML文件 > 环境变量(OPENAI_API_KEY) > 默认值
"""

import os
import sys

from agentcore import AgentCore

ROOT = os.path.dirname(os.path.abspath(__file__))

# ── 导入各模块（导入即触发 auto_register 扫描） ──────────
import tools

# ── 启动应用 ──────────────────────────────────────────
app = AgentCore(
    name="MyAgent",
    log_path=os.path.join(ROOT, "logs", "agentcore.jsonl"),
)

app.auto_register(tools)


# ── 启动入口 ──────────────────────────────────────────
if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        sys.exit(0)

    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        app.run(query=" ".join(sys.argv[1:]))
    else:
        app.run()
