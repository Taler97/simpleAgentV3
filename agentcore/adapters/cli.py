"""交互式 CLI - 提供命令行对话界面。"""

import argparse
import logging
import signal
import sys
from threading import Event

from agentcore.adapters.builder import AgentBuilder
from agentcore.services.logger.file_logger import FileLogger

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="AgentCore V3 交互式 CLI")
    parser.add_argument("-c", "--config", default="resources/config.yaml", help="配置文件路径")
    parser.add_argument("--log", default="agentcore.log.jsonl", help="日志文件路径")
    args = parser.parse_args()

    # 构建 Agent
    logger.info("正在从 %s 加载配置...", args.config)
    try:
        agent = AgentBuilder.from_yaml(args.config).build()
    except FileNotFoundError:
        logger.error("配置文件未找到: %s", args.config)
        sys.exit(1)

    # 注册日志监听器
    file_logger = FileLogger(args.log)
    agent.add_listener("file_logger", lambda record: file_logger.write(record))

    # 处理 Ctrl+C
    cancel_event = Event()

    def _signal_handler(sig, frame):
        print("\n[正在取消...]")
        cancel_event.set()

    signal.signal(signal.SIGINT, _signal_handler)

    print("AgentCore V3 CLI (输入 'exit' 退出, 'clear' 清屏)")
    print("-" * 50)

    while True:
        try:
            user_input = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("再见！")
            break
        if user_input.lower() == "clear":
            import os
            os.system("cls" if os.name == "nt" else "clear")
            continue

        result = agent.chat(user_input, cancel_event=cancel_event)
        print(f"\n{result}\n")
        cancel_event.clear()

    agent.shutdown()


if __name__ == "__main__":
    main()
