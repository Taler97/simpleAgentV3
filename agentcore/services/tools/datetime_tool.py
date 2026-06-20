"""日期时间工具 - 返回当前日期和时间。"""

from typing import Any, Dict

from datetime import datetime


class DatetimeTool:
    name = "datetime"
    description = "获取当前日期和时间信息"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "format": {
                "type": "string",
                "description": "日期格式，默认为 %Y-%m-%d %H:%M:%S",
                "default": "%Y-%m-%d %H:%M:%S",
            }
        },
    }

    def execute(self, input_str: str) -> str:
        """执行工具，返回当前时间字符串。"""
        # 简单的格式解析
        fmt = input_str.strip() or "%Y-%m-%d %H:%M:%S"
        try:
            return datetime.now().strftime(fmt)
        except Exception as e:
            return f"格式错误: {e}"
