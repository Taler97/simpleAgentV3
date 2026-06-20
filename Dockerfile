# AgentCore V3 — 生产级 AI Agent 运行底座
FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e . && pip install --no-cache-dir ".[dev]"

# 复制源码
COPY agentcore/ ./agentcore/

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# 默认命令：启动健康检查服务
CMD ["python", "-m", "agentcore.contrib.http_server.health_server"]
