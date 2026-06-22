"""文件读取工具 - 读取本地文件内容。"""

import os
from agentcore.adapters.decorators import tool


@tool
def read_file(path: str) -> str:
    """读取本地文件内容。path 可以是相对路径或绝对路径。"""
    try:
        resolved = os.path.abspath(path)
        with open(resolved, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"文件不存在: {path}"
    except IsADirectoryError:
        return f"路径是一个目录: {path}"
    except Exception as e:
        return f"读取文件失败: {e}"
