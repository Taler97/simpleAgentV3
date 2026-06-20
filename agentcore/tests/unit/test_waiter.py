"""SyncWaiter 单元测试。"""

import time
from threading import Event

from agentcore.runtime.waiter import SyncWaiter


class TestSyncWaiter:
    def test_normal_execution(self):
        waiter = SyncWaiter()
        result = waiter.run(lambda: "hello", timeout=5.0)
        assert result == "hello"
        waiter.shutdown()

    def test_timeout(self):
        waiter = SyncWaiter()
        result = waiter.run(lambda: time.sleep(10) or "done", timeout=1.0)
        assert result.startswith("Timeout after")
        waiter.shutdown()

    def test_cancelled(self):
        waiter = SyncWaiter()
        cancel = Event()
        cancel.set()  # 预置取消
        result = waiter.run(lambda: "done", timeout=5.0, cancel_event=cancel)
        assert result == "Cancelled"
        waiter.shutdown()

    def test_error(self):
        waiter = SyncWaiter()

        def _raise():
            raise ValueError("something wrong")

        result = waiter.run(_raise, timeout=5.0)
        assert "Error:" in result
        assert "something wrong" in result
        waiter.shutdown()

    def test_return_str(self):
        waiter = SyncWaiter()
        result = waiter.run(lambda: 42, timeout=5.0)
        assert result == "42"
        assert isinstance(result, str)
        waiter.shutdown()
