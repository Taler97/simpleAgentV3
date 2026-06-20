"""Checkpointer 单元测试。"""

import os
import tempfile

from agentcore.runtime.checkpointer import FileCheckpointer


class TestFileCheckpointer:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ckpt = FileCheckpointer(self.tmpdir)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _sample_state(self, **overrides):
        state = {
            "session_id": "test-session",
            "trace_id": "abc123",
            "step": 3,
            "messages": [
                {"role": "system", "content": "You are a helper"},
                {"role": "user", "content": "1+1等于几？"},
            ],
            "step_records": [
                {"step": 1, "action": "calculator", "action_input": "{\"expression\": \"1+1\"}", "thought": "计算", "observation": "2", "result": ""},
                {"step": 2, "action": "calculator", "action_input": "{\"expression\": \"2+2\"}", "thought": "再算", "observation": "4", "result": ""},
            ],
            "user_input": "1+1等于几？",
            "max_steps": 10,
            "parent_skill_id": None,
            "status": "in_progress",
            "result": "",
        }
        state.update(overrides)
        return state

    def test_save_and_load(self):
        state = self._sample_state()
        self.ckpt.save("test-session", state)
        loaded = self.ckpt.load("test-session")
        assert loaded is not None
        assert loaded["session_id"] == "test-session"
        assert loaded["step"] == 3
        assert loaded["status"] == "in_progress"
        assert len(loaded["messages"]) == 2
        assert len(loaded["step_records"]) == 2

    def test_load_nonexistent(self):
        loaded = self.ckpt.load("no-such-session")
        assert loaded is None

    def test_delete(self):
        self.ckpt.save("test-session", self._sample_state())
        self.ckpt.delete("test-session")
        loaded = self.ckpt.load("test-session")
        assert loaded is None

    def test_overwrite(self):
        self.ckpt.save("test-session", self._sample_state(step=1, status="in_progress"))
        self.ckpt.save("test-session", self._sample_state(step=5, status="completed", result="42"))
        loaded = self.ckpt.load("test-session")
        assert loaded["step"] == 5
        assert loaded["status"] == "completed"
        assert loaded["result"] == "42"

    def test_list_sessions(self):
        self.ckpt.save("session-a", self._sample_state(session_id="session-a"))
        self.ckpt.save("session-b", self._sample_state(session_id="session-b"))
        sessions = self.ckpt.list_sessions()
        assert "session-a" in sessions
        assert "session-b" in sessions

    def test_large_messages(self):
        """验证大数据量下 checkpointer 仍正常工作。"""
        messages = [{"role": "user", "content": f"第{i}条消息 " * 50} for i in range(20)]
        state = self._sample_state(messages=messages)
        self.ckpt.save("large-session", state)
        loaded = self.ckpt.load("large-session")
        assert loaded is not None
        assert len(loaded["messages"]) == 20

    def test_atomic_save_on_crash(self):
        """模拟写入时崩溃：.tmp 文件不应被当做有效检查点。"""
        state = self._sample_state()
        self.ckpt.save("crash-session", state)

        # 手动创建一个 .tmp 文件模拟崩溃
        tmp_path = self.ckpt._path("crash-session") + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write("{corrupted json")
        # 确保 tmp 文件不干扰正常加载
        loaded = self.ckpt.load("crash-session")
        assert loaded is not None
        assert loaded["step"] == 3
