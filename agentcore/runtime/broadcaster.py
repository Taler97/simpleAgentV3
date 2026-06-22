"""Broadcaster - 线程池分发事件。"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, List

from agentcore.core.orchestrator import StepRecord

logger = logging.getLogger(__name__)


class ErrorHandler:
    """默认错误处理器，打印异常日志。"""

    def handle(self, listener_name: str, record: StepRecord, exception: Exception) -> None:
        logger.error("Listener '%s' failed for step %d: %s", listener_name, record.step, exception)


class Broadcaster:
    """事件分发器。

    使用线程池并发分发 StepRecord 到所有已注册的监听器。
    任一监听器抛出异常不影响其他监听器。
    """

    def __init__(
        self,
        pool: ThreadPoolExecutor,
        error_handler: ErrorHandler = None,
    ):
        self._pool = pool
        self._listeners: List[tuple[str, Callable[[StepRecord], None]]] = []
        self._error_handler = error_handler or ErrorHandler()

    def register(self, name: str, listener: Callable[[StepRecord], None]) -> None:
        """注册一个监听器。"""
        self._listeners.append((name, listener))

    def publish(self, record: StepRecord) -> None:
        """分发 StepRecord 到所有监听器。"""
        for name, listener in self._listeners:
            self._pool.submit(self._safe_dispatch, name, listener, record)

    def _safe_dispatch(self, name: str, listener: Callable, record: StepRecord) -> None:
        """安全分发，异常不扩散。"""
        try:
            listener(record)
        except Exception as e:
            self._error_handler.handle(name, record, e)
