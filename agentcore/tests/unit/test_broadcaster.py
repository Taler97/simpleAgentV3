"""Broadcaster 单元测试。"""

import time
from concurrent.futures import ThreadPoolExecutor

from agentcore.core.orchestrator import StepRecord
from agentcore.runtime.broadcaster import Broadcaster


class TestBroadcaster:
    def test_publish_calls_listeners(self):
        pool = ThreadPoolExecutor(max_workers=2)
        bc = Broadcaster(pool)
        results = []

        def listener(record):
            results.append(record.step)

        bc.register("test", listener)
        record = StepRecord(step=1, action="", action_input="", thought="test")
        bc.publish(record)
        time.sleep(0.2)  # 等待异步执行
        assert len(results) == 1
        assert results[0] == 1
        pool.shutdown()

    def test_listener_exception_isolated(self):
        pool = ThreadPoolExecutor(max_workers=2)
        bc = Broadcaster(pool)
        results = []

        def bad_listener(record):
            raise ValueError("bad!")

        def good_listener(record):
            results.append(record.step)

        bc.register("bad", bad_listener)
        bc.register("good", good_listener)
        record = StepRecord(step=2, action="", action_input="", thought="test")
        bc.publish(record)
        time.sleep(0.2)
        assert len(results) == 1
        assert results[0] == 2
        pool.shutdown()
