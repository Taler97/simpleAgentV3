"""内存滑动窗口实现的记忆存储。"""

from typing import Any, Dict, List


class SlidingWindowMemory:
    """内存滑动窗口记忆，按 session_id 存储最近 N 轮对话。"""

    def __init__(self, window_size: int = 10):
        self._window_size = window_size
        self._sessions: Dict[str, List[Dict[str, str]]] = {}

    def save(self, record: Any) -> None:
        if not isinstance(record, dict):
            return
        session_id = record.get("session_id", "default")
        entry = {"role": record["role"], "content": record["content"]}
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append(entry)
        # 裁剪窗口
        if len(self._sessions[session_id]) > self._window_size * 2:
            self._sessions[session_id] = self._sessions[session_id][-self._window_size * 2:]

    def get_context(self, session_id: str = "default") -> List[Dict[str, str]]:
        return self._sessions.get(session_id, [])

    def clear(self) -> None:
        self._sessions.clear()
