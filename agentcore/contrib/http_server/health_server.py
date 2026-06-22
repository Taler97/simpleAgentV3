"""轻量健康检查 HTTP 服务器"""

import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from agentcore.adapters.agent import Agent


_HEALTH_HTML = """<!DOCTYPE html>
<html>
<head><title>AgentCore Health</title></head>
<body>
<h1>AgentCore V3</h1>
<p>Status: <span style="color:green">Running</span></p>
</body>
</html>"""


class _HealthHandler(BaseHTTPRequestHandler):
    """处理 /health 和 / 请求。"""

    agent: Optional[Agent] = None
    start_time: float = time.time()

    def do_GET(self):
        if self.path == "/health":
            self._json_response(200, {
                "status": "ok",
                "service": "agentcore-v3",
                "uptime_seconds": int(time.time() - self.start_time),
                "version": "3.0.0",
            })
        elif self.path == "/":
            self._html_response(200, _HEALTH_HTML)
        else:
            self._json_response(404, {"error": "not_found"})

    def _json_response(self, code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html_response(self, code: int, html: str):
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # 静默日志


def serve_health(agent: Optional[Agent] = None, host: str = "0.0.0.0", port: int = 8080):
    """启动健康检查 HTTP 服务器（阻塞）。"""
    _HealthHandler.agent = agent
    server = HTTPServer((host, port), _HealthHandler)
    print(f"[AgentCore] Health server listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[AgentCore] Health server stopped")
        server.server_close()
