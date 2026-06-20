"""Parser - LLM 响应的容错 JSON 解析。"""

import json
import re
from typing import Any, Dict


class Parser:
    """容错 JSON 解析器，处理 LLM 常见的 JSON 格式问题。"""

    @staticmethod
    def parse(raw: str) -> Dict[str, Any]:
        """解析 LLM 响应字符串为字典。支持容错处理。"""
        text = raw.strip()

        # 尝试直接解析
        if text.startswith("{"):
            return _parse_json(text)

        # 提取 markdown 代码块中的 JSON
        block = _extract_code_block(text)
        if block:
            return _parse_json(block)

        # 尝试从文本中查找第一个 { 到最后一个 }
        first = text.find("{")
        last = text.rfind("}")
        if first != -1 and last > first:
            return _parse_json(text[first:last + 1])

        raise ValueError(f"无法从响应中提取 JSON:\n{raw[:200]}")


def _parse_json(text: str) -> Dict[str, Any]:
    """带容错处理的 JSON 解析。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 修复常见问题后重试
    cleaned = _clean_json(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败 (cleaned): {e}\n原始内容:\n{text[:300]}")


def _clean_json(text: str) -> str:
    """清理 JSON 字符串中的常见格式问题。"""
    # 移除注释 (// 和 /* */)
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)

    # 移除多余的尾部逗号
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)

    # 将单引号替换为双引号（适用于 key 和 string value）
    # 先替换 key 的单引号: 'key': -> "key":
    text = re.sub(r"'([^']+)'\s*:", r'"\1":', text)
    # 再替换 value 的单引号: : 'value' -> : "value"
    text = re.sub(r":\s*'([^']*)'", r': "\1"', text)
    return text


def _extract_code_block(text: str) -> str:
    """提取 markdown 代码块中的内容。"""
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""
