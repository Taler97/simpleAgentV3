"""文件写入工具 — 写入内容到文件。"""

import os
from agentcore.adapters.decorators import tool
from ._confirm import confirm

_PREVIEW_CHARS = 200


@tool
def write_file(path: str, content: str) -> str:
    """将内容写入指定文件。path 为文件路径，content 为要写入的内容。"""
    try:
        resolved = os.path.abspath(path)
    except Exception as e:
        return f"错误: 路径无效 - {e}"

    preview = content[:_PREVIEW_CHARS]
    if len(content) > _PREVIEW_CHARS:
        preview += f"\n...（共 {len(content)} 字符，仅预览前 {_PREVIEW_CHARS} 字符）"

    detail = f"文件: {resolved}\n\n内容预览:\n{preview}"

    if not confirm("写入文件", detail):
        return "已取消: 用户拒绝了该操作"

    try:
        os.makedirs(os.path.dirname(resolved) or ".", exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)
        return f"文件已写入: {resolved}"
    except Exception as e:
        return f"写入失败: {e}"
