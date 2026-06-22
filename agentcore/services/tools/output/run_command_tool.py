"""命令执行工具 — 在终端中执行命令。"""

import re
import subprocess
from agentcore.adapters.decorators import tool
from ._confirm import confirm

# ── 黑名单 ──────────────────────────────────────────

_BLOCKED_COMMANDS = frozenset({
    "format", "shutdown", "reboot", "restart",
    "taskkill", "kill",
    "chkdsk", "diskpart", "bootrec", "bcdedit",
    "reg", "regedit",
})

_BLOCKED_PATTERNS = [
    re.compile(r"rm\s+[-/][rf].*", re.IGNORECASE),
    re.compile(r"rd\s+[-/]s.*", re.IGNORECASE),
    re.compile(r"rmdir\s+[-/]s.*", re.IGNORECASE),
    re.compile(r"del\s+[-/]f.*", re.IGNORECASE),
    re.compile(r"fsutil", re.IGNORECASE),
    re.compile(r"cipher", re.IGNORECASE),
]

_CMD_TIMEOUT = 30


# ── 工具函数 ─────────────────────────────────────────


def _is_blocked(command: str) -> str | None:
    """检查命令是否被禁止。返回 None 表示通过，否则返回错误信息。"""
    first_word = command.split()[0].lower() if command.split() else ""
    if first_word in _BLOCKED_COMMANDS:
        return f"错误: 命令 '{first_word}' 被禁止执行"

    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(command):
            return "错误: 命令匹配危险模式，已拒绝"

    return None


@tool
def run_command(command: str, reason: str = "") -> str:
    """在终端中执行命令并返回输出。reason 参数应说明执行该命令的原因。"""
    command = command.strip()
    if not command:
        return "错误: 命令为空"

    # ── 黑名单检查 ──
    blocked = _is_blocked(command)
    if blocked:
        return blocked

    # ── 弹窗确认 ──
    detail = f"Agent 要执行:\n    {command}"
    detail += f"\n  原因: {reason}" if reason else "\n  原因: 未说明"

    if not confirm("操作确认", detail):
        return "已取消: 用户拒绝了该操作"

    # ── 执行 ──
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=_CMD_TIMEOUT,
        )
        output = []
        if result.stdout:
            output.append(result.stdout.strip())
        if result.stderr:
            output.append(f"[stderr]\n{result.stderr.strip()}")
        return "\n".join(output) if output else "命令执行完毕（无输出）"
    except subprocess.TimeoutExpired:
        return f"错误: 命令执行超时（{_CMD_TIMEOUT}秒）"
    except Exception as e:
        return f"错误: 执行失败 - {e}"
