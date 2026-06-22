"""交互式 CLI — AgentCore V3 唯一入口。

运行方式:
    agentcore                      # 交互式对话
    agentcore "1+1等于几？"         # 单次提问
    agentcore -c 配置文件.yaml      # 指定配置文件
"""

import argparse
import logging
import os
import sys
from agentcore import AgentCore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="AgentCore V3 — 生产级 AI Agent 运行底座")
    parser.add_argument("query", nargs="?", default="", help="单次提问内容（不传则进入交互模式）")
    parser.add_argument("-c", "--config", default="", help="配置文件路径（默认 resources/config.yaml）")
    args = parser.parse_args()

    # ── 定位配置文件 ──────────────────────────────────
    root = os.path.dirname(os.path.abspath(__file__))
    config_path = args.config or os.path.join(root, "..", "..", "resources", "config.yaml")

    # ── 构建 AgentCore ────────────────────────────────
    app = AgentCore(config_path=config_path)

    # ── 自动注册 @tool 工具 ────────────────────────────
    try:
        from agentcore.services import tools as fw_tools
        app.auto_register(fw_tools)
    except ImportError:
        logger.warning("未找到 services.tools 模块，跳过工具自动注册")

    # ── 运行 ──────────────────────────────────────────
    app.run(query=args.query)


if __name__ == "__main__":
    main()
