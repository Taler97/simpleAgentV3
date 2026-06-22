"""接口定义 - 所有可插拔组件的抽象接口。"""

from typing import Any, Dict, Iterator, List, Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """LLM 客户端接口。"""

    def generate(
        self,
        messages: List[Dict[str, str]],
        response_format: Any = None,
        stream: bool = False,
    ) -> str | Iterator[str]:
        """输入消息列表，返回生成文本。

        当 stream=True 时返回 Iterator[str]（逐 token 产出），
        否则返回完整 str。

        Args:
            messages: 对话消息列表
            response_format: OpenAI 格式的 response_format 参数
            stream: 是否启用流式输出
        """
        ...


@runtime_checkable
class MemoryInterface(Protocol):
    """记忆存储接口。"""

    def save(self, record: Any) -> None:
        """保存一条记忆记录。"""
        ...

    def get_context(self, session_id: str) -> List[Dict[str, str]]:
        """获取指定会话的上下文消息列表。"""
        ...

    def clear(self) -> None:
        """清空所有记忆。"""
        ...


class LoggerInterface(Protocol):
    """日志持久化接口。"""

    def write(self, record: Any) -> None:
        """写入一条日志记录。"""
        ...


class ToolInterface(Protocol):
    """工具定义接口。"""
    name: str
    description: str
    parameters_schema: Dict[str, Any]

    def execute(self, input_str: str) -> str:
        """执行工具，输入输出均为字符串。"""
        ...
