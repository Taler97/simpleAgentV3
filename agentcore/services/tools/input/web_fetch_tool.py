"""网页抓取工具 - 获取网页文本内容。"""

import re

import requests
from agentcore.adapters.decorators import tool

_MAX_CHARS = 3000


@tool
def web_fetch(url: str) -> str:
    """获取指定 URL 的网页文本内容。适用于阅读文章、文档页面等。"""
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; AgentCore/3.0)"
        })
        resp.raise_for_status()
    except Exception as e:
        return f"获取网页失败: {e}"

    text = resp.text

    # 提取 <body> 纯文本
    body_match = re.search(r"<body[^>]*>(.*?)</body>", text, re.DOTALL | re.IGNORECASE)
    if body_match:
        text = body_match.group(1)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > _MAX_CHARS:
        text = text[:_MAX_CHARS] + f"\n\n...（已截断，原文共 {len(text)} 字符）"

    return text
