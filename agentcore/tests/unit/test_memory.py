"""SlidingWindowMemory 单元测试。"""

from agentcore.services.memory.sliding_window import SlidingWindowMemory


class TestSlidingWindowMemory:
    def test_save_and_get_context(self):
        mem = SlidingWindowMemory(window_size=3)
        mem.save({"role": "user", "content": "hi", "session_id": "s1"})
        mem.save({"role": "assistant", "content": "hello", "session_id": "s1"})
        ctx = mem.get_context("s1")
        assert len(ctx) == 2
        assert ctx[0]["content"] == "hi"
        assert ctx[1]["content"] == "hello"

    def test_session_isolation(self):
        mem = SlidingWindowMemory()
        mem.save({"role": "user", "content": "a", "session_id": "s1"})
        mem.save({"role": "user", "content": "b", "session_id": "s2"})
        assert len(mem.get_context("s1")) == 1
        assert len(mem.get_context("s2")) == 1

    def test_window_sliding(self):
        mem = SlidingWindowMemory(window_size=1)
        for i in range(5):
            mem.save({"role": "user", "content": str(i), "session_id": "s1"})
        ctx = mem.get_context("s1")
        # window_size * 2 = 2 条最多
        assert len(ctx) <= 2

    def test_clear(self):
        mem = SlidingWindowMemory()
        mem.save({"role": "user", "content": "x", "session_id": "s1"})
        mem.clear()
        assert mem.get_context("s1") == []

    def test_invalid_record(self):
        mem = SlidingWindowMemory()
        mem.save("not a dict")  # 不应报错
        assert mem.get_context("default") == []
