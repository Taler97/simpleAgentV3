"""Redis 实现的记忆存储。"""

import json
from typing import Any, Dict, List


class RedisMemory:
    """基于 Redis 的持久化记忆存储。"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str = "",
        ttl: int = 3600,
        key_prefix: str = "agentcore:memory:",
    ):
        import redis

        self._ttl = ttl
        self._key_prefix = key_prefix
        self._client = redis.Redis(host=host, port=port, db=db, password=password or None)

    def _session_key(self, session_id: str) -> str:
        return f"{self._key_prefix}{session_id}"

    def save(self, record: Any) -> None:
        if not isinstance(record, dict):
            return
        key = self._session_key(record.get("session_id", "default"))
        entry = json.dumps({"role": record["role"], "content": record["content"]})
        self._client.rpush(key, entry)
        self._client.expire(key, self._ttl)

    def get_context(self, session_id: str = "default") -> List[Dict[str, str]]:
        key = self._session_key(session_id)
        items = self._client.lrange(key, 0, -1)
        return [json.loads(item) for item in items]

    def clear(self) -> None:
        for key in self._client.scan_iter(match=f"{self._key_prefix}*"):
            self._client.delete(key)
