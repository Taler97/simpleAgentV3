"""文本搜索工具 - 在文件中搜索文本。"""

import glob as glob_module
import os
import re
from agentcore.adapters.decorators import tool

_TEXT_EXTENSIONS = (
    "*.py", "*.txt", "*.md", "*.json", "*.yaml", "*.yml", "*.toml",
    "*.cfg", "*.ini", "*.conf",
    "*.js", "*.ts", "*.jsx", "*.tsx", "*.html", "*.css",
    "*.rs", "*.go", "*.java", "*.c", "*.h", "*.cpp", "*.hpp",
)

_MAX_RESULTS = 60


@tool
def grep_search(pattern: str, path: str = ".") -> str:
    """在文件中搜索文本（正则匹配）。path 指定目录或文件，默认为当前目录。"""
    try:
        target_path = os.path.abspath(path)

        if os.path.isfile(target_path):
            files = [target_path]
        else:
            files = []
            for ext in _TEXT_EXTENSIONS:
                files.extend(
                    glob_module.glob(os.path.join(target_path, "**", ext), recursive=True)
                )

        compiled = re.compile(pattern, re.MULTILINE)
        results = []
        for fp in files:
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    for lineno, line in enumerate(f, 1):
                        if compiled.search(line):
                            results.append(
                                f"{os.path.relpath(fp, target_path)}:{lineno}: {line.rstrip()}"
                            )
            except Exception:
                continue

        if not results:
            return f"未找到匹配的内容: {pattern}"

        output = "\n".join(results[:_MAX_RESULTS])
        if len(results) > _MAX_RESULTS:
            output += f"\n\n...（共 {len(results)} 条匹配，仅显示前 {_MAX_RESULTS} 条）"
        return output
    except Exception as e:
        return f"搜索失败: {e}"
