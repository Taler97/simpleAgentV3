"""网络搜索工具 - 搜索互联网信息。"""

from duckduckgo_search import DDGS
from agentcore.adapters.decorators import tool


@tool
def web_search(query: str) -> str:
    """搜索互联网，返回标题、摘要和链接。适用于查询实时信息、新闻、文档等。"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
    except Exception as e:
        return f"搜索失败: {e}"

    if not results:
        return "未找到相关结果。"

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   {r['body']}")
        lines.append(f"   {r['href']}")
    return "\n".join(lines)
