"""SyncWaiter - 线程池执行守卫，提供超时与取消支持。"""

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from threading import Event
from typing import Callable, Optional


class SyncWaiter:
    """同步执行守卫。

    将函数提交到线程池执行，主线程以 0.5s 脉冲间隔检查超时与取消信号。
    所有返回值统一为 str 类型，不向上抛出异常。
    """

    def __init__(self, pool: Optional[ThreadPoolExecutor] = None):
        self._pool = pool or ThreadPoolExecutor(max_workers=4)

    def run(
        self,
        func: Callable[[], str],
        timeout: float = 30.0,
        cancel_event: Optional[Event] = None,
    ) -> str:
        """执行函数并等待结果。

        返回说明：
        - 正常结果 → 返回函数返回值
        - 超时 → 返回 "Timeout after Xs"
        - 取消 → 返回 "Cancelled"
        - 异常 → 返回 "Error: {str(e)}"
        """
        future = self._pool.submit(func)
        start = time.monotonic()
        elapsed = 0.0

        while elapsed < timeout:
            # 检查取消信号
            if cancel_event and cancel_event.is_set():
                future.cancel()
                return "Cancelled"

            # 以 0.5s 脉冲间隔检查 future 是否完成
            try:
                result = future.result(timeout=0.5)
                return str(result)
            except FutureTimeout:
                pass
            except Exception as e:
                return f"Error: {e}"

            elapsed = time.monotonic() - start

        # 超时
        future.cancel()
        return f"Timeout after {timeout}s"

    def shutdown(self, wait: bool = True) -> None:
        """关闭线程池。"""
        self._pool.shutdown(wait=wait)
