"""MCP (Model Context Protocol) 客户端适配器。

通过 STDIO 传输与 MCP Server 通信，将 MCP 工具转换为 _ToolWrapper 实例。
使用方式:

    from agentcore.mcp import MCPClient

    client = MCPClient(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "."])
    tools = client.list_tools()          # → List[_ToolWrapper]
    for t in tools:
        agent.add_tool(t)
    client.close()
"""

import json
import os
import shutil
import subprocess
import threading
from typing import Any, Dict, List, Optional

from agentcore.adapters.decorators import _ToolWrapper


class MCPError(Exception):
    """MCP 协议错误。"""


class MCPClient:
    """轻量 MCP 客户端，通过 STDIO 传输与 MCP Server 通信。"""

    def __init__(
        self,
        command: str,
        args: Optional[List[str]] = None,
        server_name: str = "mcp-server",
    ):
        self._server_name = server_name
        # 解析命令的完整路径（Windows 上 .cmd/.bat 文件需要）
        cmd = shutil.which(command)
        if cmd is None:
            cmd = command
        self._proc = subprocess.Popen(
            [cmd, *(args or [])],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._lock = threading.Lock()
        self._next_id = 1
        self._buffer = ""
        self._init()

    # ── 生命周期 ──────────────────────────────────────

    def _init(self) -> None:
        """初始化 MCP 连接。"""
        result = self._request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "agentcore", "version": "3.0.0"},
        })
        # 发送 initialized 通知（协议要求）
        self._notify("notifications/initialized")

    def list_tools(self) -> List[_ToolWrapper]:
        """获取 MCP Server 提供的所有工具，返回 _ToolWrapper 列表。"""
        result = self._request("tools/list")
        tools_data = result.get("tools", [])
        wrappers = []
        for t in tools_data:
            wrapper = self._mcp_tool_to_wrapper(t)
            wrappers.append(wrapper)
        return wrappers

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """调用 MCP 工具，返回文本结果。"""
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content", [])
        texts = []
        for item in content:
            if item.get("type") == "text":
                texts.append(item.get("text", ""))
        return "\n".join(texts) if texts else str(result)

    def close(self) -> None:
        """关闭 MCP Server 连接。"""
        try:
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except Exception:
            self._proc.kill()

    # ── JSON-RPC 通信 ─────────────────────────────────

    def _request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发送 JSON-RPC 请求，等待响应。"""
        with self._lock:
            req_id = self._next_id
            self._next_id += 1
            payload = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
            }
            if params is not None:
                payload["params"] = params
            self._send(payload)
            return self._recv(req_id)

    def _notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """发送 JSON-RPC 通知（无响应）。"""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        self._send(payload)

    def _send(self, payload: Dict[str, Any]) -> None:
        """写入一行 JSON 到 server stdin。"""
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        self._proc.stdin.write(line)
        self._proc.stdin.flush()

    def _recv(self, expected_id: int) -> Dict[str, Any]:
        """从 server stdout 读取响应，匹配指定 id。"""
        while True:
            # 从缓冲区读取完整行
            while "\n" not in self._buffer:
                chunk = self._proc.stdout.readline()
                if not chunk:
                    raise MCPError("MCP Server 连接已关闭")
                self._buffer += chunk

            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue  # 忽略非 JSON 输出

            # 忽略服务端通知（没有 id）
            if "id" not in msg:
                continue

            if msg.get("id") != expected_id:
                continue

            if "error" in msg:
                err = msg["error"]
                raise MCPError(f"MCP 错误: {err.get('message', str(err))}")

            return msg.get("result", {})

    # ── 工具转换 ──────────────────────────────────────

    def _mcp_tool_to_wrapper(self, tool_def: Dict[str, Any]) -> _ToolWrapper:
        """将 MCP 工具定义转换为 _ToolWrapper。"""
        name = tool_def["name"]
        description = tool_def.get("description", "")
        input_schema = tool_def.get("inputSchema", {"type": "object", "properties": {}})

        # 创建一个模拟函数，使其满足 _ToolWrapper 的契约
        def make_fn(tool_name: str, schema: Dict[str, Any]):
            def fn(**kwargs) -> str:
                return self.call_tool(tool_name, kwargs)
            fn.__name__ = tool_name
            fn.__qualname__ = f"MCPTool.{tool_name}"
            fn.__doc__ = description
            return fn

        func = make_fn(name, input_schema)
        wrapper = _ToolWrapper(func)

        # _ToolWrapper 从 type hints 推断 schema，但 MCP 有它自己的 schema
        # 替换为 MCP server 提供的 schema
        mcp_props = input_schema.get("properties", {})
        mcp_required = input_schema.get("required", [])
        wrapper.parameters_schema = {
            "type": "object",
            "properties": {
                pname: {
                    "type": pinfo.get("type", "string"),
                    "description": pinfo.get("description", f"参数 {pname}"),
                }
                for pname, pinfo in mcp_props.items()
            },
            "required": mcp_required,
        }

        return wrapper
