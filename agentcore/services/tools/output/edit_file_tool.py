"""文件编辑工具 — 搜索替换文件内容。"""

import os
from agentcore.adapters.decorators import tool
from ._confirm import confirm

_DIFF_CONTEXT = 80


@tool
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """在文件中搜索 old_text 并替换为 new_text。仅替换首次匹配。"""
    try:
        resolved = os.path.abspath(path)
        with open(resolved, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return f"错误: 文件不存在 - {path}"
    except Exception as e:
        return f"错误: 读取文件失败 - {e}"

    if old_text not in content:
        return "错误: 未在文件中找到匹配内容"

    # ── 构建修改对比预览 ──
    idx = content.index(old_text)
    ctx_before = content[max(0, idx - _DIFF_CONTEXT):idx]
    ctx_after = content[idx + len(old_text):idx + len(old_text) + _DIFF_CONTEXT]

    detail = (
        f"文件: {resolved}\n\n"
        f"--- 修改前 ---\n"
        f"...{ctx_before}[{old_text}]{ctx_after}...\n\n"
        f"--- 修改后 ---\n"
        f"...{ctx_before}[{new_text}]{ctx_after}..."
    )

    if not confirm("编辑文件", detail):
        return "已取消: 用户拒绝了该操作"

    # ── 执行替换 ──
    try:
        new_content = content.replace(old_text, new_text, 1)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(new_content)
        return f"文件已修改: {resolved}（替换 1 处）"
    except Exception as e:
        return f"写入失败: {e}"
