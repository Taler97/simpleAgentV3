"""文件查找工具 - 按 glob 模式查找文件路径。"""

import glob as glob_module
from agentcore.adapters.decorators import tool

_MAX_RESULTS = 50


@tool
def glob(pattern: str) -> str:
    """按 glob 模式查找文件路径。例如: **/*.py, src/**/*.ts, *.md"""
    try:
        matches = glob_module.glob(pattern, recursive=True)
        if not matches:
            return f"未找到匹配的文件: {pattern}"
        output = "\n".join(matches[:_MAX_RESULTS])
        if len(matches) > _MAX_RESULTS:
            output += f"\n\n...（共 {len(matches)} 个，仅显示前 {_MAX_RESULTS} 个）"
        return output
    except Exception as e:
        return f"查找文件失败: {e}"
