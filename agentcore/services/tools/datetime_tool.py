"""日期时间工具 - 返回当前日期和时间。"""

from datetime import datetime as _dt
from agentcore.adapters.decorators import tool


@tool
def datetime(format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前日期和时间信息"""
    try:
        return _dt.now().strftime(format)
    except Exception as e:
        return f"格式错误: {e}"
