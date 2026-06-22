"""Checkpointer - Agent 执行状态检查点，支持崩溃恢复。

Checkpointer ≠ Memory:
  - Memory 存的是"对话结果"（user/assistant 对话历史）
  - Checkpointer 存的是"执行中间状态"（messages 列表 + 当前步骤号）

恢复流程:
  1. 用户再次调用 agent.chat() 或 agent.resume(session_id)
  2. Orchestrator 检测到 session_id 有 in_progress 的检查点
  3. 直接恢复 messages 列表和起始步骤，继续执行
  4. 完成后清除检查点
"""

import json
import os
from typing import Any, Dict, List, Optional

# ── 检查点数据结构 ──────────────────────────────────────
#
# Checkpoint 的 JSON 格式:
# {
#     "session_id": "default",
#     "trace_id": "abc...",
#     "step": 3,              # 已完成的最大步骤
#     "messages": [...],      # 完整的 LLM messages 列表（系统 prompt + 历史 + 已执行步骤）
#     "user_input": "...",    # 用户原始输入
#     "max_steps": 10,
#     "parent_skill_id": null,
#     "status": "in_progress", # 或 "completed" / "failed"
#     "step_records": [...],  # 已产生的 StepRecord 列表
#     "result": "",           # 仅在 status=completed 时有值
# }


class BaseCheckpointer:
    """检查点存储基类。"""

    def save(self, session_id: str, state: Dict[str, Any]) -> None:
        """保存检查点。"""
        raise NotImplementedError

    def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """加载检查点，不存在时返回 None。"""
        raise NotImplementedError

    def delete(self, session_id: str) -> None:
        """删除检查点。"""
        raise NotImplementedError

    def list_sessions(self) -> List[str]:
        """列出所有有检查点的 session_id。"""
        raise NotImplementedError


class NullCheckpointer(BaseCheckpointer):
    """空检查点 — 所有方法无操作，用于禁用检查点功能。"""

    def save(self, session_id: str, state: Dict[str, Any]) -> None:
        pass

    def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        return None

    def delete(self, session_id: str) -> None:
        pass

    def list_sessions(self) -> List[str]:
        return []


class FileCheckpointer(BaseCheckpointer):
    """基于本地文件的检查点存储。

    每个 session 一个 JSON 文件，存放在指定目录下。
    适合单实例部署场景。
    """

    def __init__(self, dir_path: str = ".checkpoints"):
        self._dir = dir_path
        os.makedirs(self._dir, exist_ok=True)

    def _safe_name(self, session_id: str) -> str:
        """将 session_id 转为安全的文件名。"""
        return session_id.replace("/", "_").replace("\\", "_").replace(":", "_")

    def _path(self, session_id: str) -> str:
        return os.path.join(self._dir, f"{self._safe_name(session_id)}.ckpt.json")

    def save(self, session_id: str, state: Dict[str, Any]) -> None:
        path = self._path(session_id)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        # 原子替换，防止写一半崩溃导致文件损坏
        os.replace(tmp_path, path)

    def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        path = self._path(session_id)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def delete(self, session_id: str) -> None:
        path = self._path(session_id)
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

    def list_sessions(self) -> List[str]:
        sessions = []
        for fname in os.listdir(self._dir):
            if fname.endswith(".ckpt.json"):
                sessions.append(fname[:-len(".ckpt.json")])
        return sessions
