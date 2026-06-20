"""JSONL 文件日志实现。"""

import json
import os
from datetime import datetime
from typing import Any


class FileLogger:
    """将 StepRecord 写入 JSONL 文件。"""

    def __init__(self, file_path: str = "agentcore.log.jsonl"):
        self._file_path = file_path
        # 确保目录存在
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)

    def write(self, record: Any) -> None:
        """写入一条日志记录。"""
        if hasattr(record, "to_dict"):
            data = record.to_dict()
        elif isinstance(record, dict):
            data = record
        else:
            data = {"raw": str(record)}

        data["_timestamp"] = datetime.utcnow().isoformat()
        with open(self._file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
