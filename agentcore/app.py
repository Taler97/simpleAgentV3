"""AgentCore — 应用启动器，提供 SpringBoot 风格的简洁声明式 API。

用法:
    from agentcore import AgentCore

    app = AgentCore()

    @app.tool
    def calculator(expression: str) -> str:
        \"\"\"计算数学表达式\"\"\"
        ...

    if __name__ == "__main__":
        app.run()
"""

import inspect
import logging
import os
import signal
import sys
from threading import Event
from typing import Any, Dict, List, Optional

from agentcore.adapters.agent import Agent
from agentcore.adapters.decorators import _ToolWrapper, tool as _tool_decorator
from agentcore.adapters.skill import SkillBase
from agentcore.core.interfaces import LLMClient, MemoryInterface
from agentcore.runtime.checkpointer import BaseCheckpointer, FileCheckpointer

logger = logging.getLogger("agentcore")


# ── AgentCore 启动器 ──────────────────────────────────

class AgentCore:
    """SpringBoot 风格的 Agent 启动器。

    自动组装 Agent、注册工具/技能、提供 run() 入口。
    配置来源优先级: YAML 文件 > 环境变量 > 默认值。
    """

    def __init__(
        self,
        name: str = "__main__",
        config_path: str = "",
        *,
        api_key: str = "",
        model: str = "gpt-4o",
        base_url: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        memory: Optional[MemoryInterface] = None,
        window_size: int = 10,
        pool_size: int = 4,
        log_path: str = "agentcore.jsonl",
        checkpointer: Optional[BaseCheckpointer] = None,
        checkpoint_dir: str = ".checkpoints",
    ):
        self._name = name
        self._log_path = log_path
        self._agent: Optional[Agent] = None
        self._builtin_tools: List[Any] = []
        self._memory: Optional[MemoryInterface] = memory
        self._detected_llm: Optional[LLMClient] = None
        self._checkpointer = checkpointer or FileCheckpointer(checkpoint_dir)

        self._config = {
            "api_key": api_key or os.environ.get("OPENAI_API_KEY", ""),
            "model": model,
            "base_url": base_url,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "window_size": window_size,
            "pool_size": pool_size,
            "log_path": log_path,
        }

        # 如果指定了配置文件，覆盖配置
        if config_path:
            self._load_config(config_path)

    def _load_config(self, path: str):
        """加载 YAML 配置文件。"""
        import yaml
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning("配置文件未找到: %s", path)
            return

        lm = cfg.get("llm", {})
        self._config.update({
            "api_key": lm.get("api_key", self._config["api_key"]),
            "model": lm.get("model", self._config["model"]),
            "base_url": lm.get("base_url", self._config["base_url"]),
            "temperature": lm.get("temperature", self._config["temperature"]),
            "max_tokens": lm.get("max_tokens", self._config["max_tokens"]),
        })

        mm = cfg.get("memory", {})
        self._config["window_size"] = mm.get("window_size", self._config["window_size"])

        rt = cfg.get("runtime", {})
        self._config["pool_size"] = rt.get("pool_size", self._config["pool_size"])

        if "log_path" in cfg:
            self._config["log_path"] = cfg["log_path"]
            self._log_path = cfg["log_path"]

        self._config["system_prompt"] = cfg.get("system_prompt", "")
        self._config["session_id"] = cfg.get("session_id", "default")

        # MCP Server 配置
        self._config["mcp_servers"] = cfg.get("mcp_servers", [])

    # ── 内部构建 Agent ────────────────────────────────

    def _build(self) -> Agent:
        """构建 Agent 实例（延迟初始化）。"""
        if self._agent is not None:
            return self._agent

        # api_key 为空时自动 fallback 到配置文件
        if not self._config["api_key"]:
            default_cfg = os.path.join(os.path.dirname(__file__), "..", "resources", "config.yaml")
            if os.path.exists(default_cfg):
                logger.info("自动加载配置文件: %s", default_cfg)
                self._load_config(default_cfg)

        from agentcore.services.memory.sliding_window import SlidingWindowMemory

        cfg = self._config

        if not cfg["api_key"] and self._detected_llm is None:
            logger.error(
                "未设置 API Key。请通过以下方式之一配置:\n"
                "  1. 编辑 resources/config.yaml 填入 api_key\n"
                "  2. 设置环境变量:  set OPENAI_API_KEY=sk-xxx\n"
                "  3. 显式传入:      AgentCore(api_key=\"sk-xxx\")"
            )
            sys.exit(1)

        # LLM: 用户模块中声明的实现优先，否则用默认 OpenAI
        llm = self._detected_llm
        if llm is None:
            try:
                from agentcore.services.llm.openai_sdk import OpenAILLM
                llm = OpenAILLM(
                    api_key=cfg["api_key"],
                    model=cfg["model"],
                    base_url=cfg["base_url"],
                    temperature=cfg["temperature"],
                    max_tokens=cfg["max_tokens"],
                )
            except ImportError:
                logger.error("需要安装 openai 依赖: pip install 'agentcore[openai]'")
                sys.exit(1)

        # 记忆: 使用用户传入的实例，或回退到默认
        memory = self._memory
        if memory is None:
            from agentcore.services.memory.sliding_window import SlidingWindowMemory
            memory = SlidingWindowMemory(window_size=cfg["window_size"])

        self._agent = Agent(
            llm=llm,
            memory=memory,
            system_prompt=cfg.get("system_prompt") or None,
            log_path=cfg["log_path"],
            pool_size=cfg["pool_size"],
            checkpointer=self._checkpointer,
        )

        # 注册已收集的内置工具
        for tool_wrapper in self._builtin_tools:
            self._agent.add_tool(tool_wrapper)

        # 注册已收集的技能
        for skill_instance in getattr(self, "_builtin_skills", []):
            self._agent.add_skill(skill_instance)

        # ── 从配置启动 MCP Server ──────────────────────
        self._mcp_clients = []
        for server_cfg in cfg.get("mcp_servers", []):
            try:
                from agentcore.mcp import MCPClient
                client = MCPClient(
                    command=server_cfg["command"],
                    args=server_cfg.get("args", []),
                    server_name=server_cfg.get("name", "mcp"),
                )
                tools = client.list_tools()
                for t in tools:
                    self._agent.add_tool(t)
                self._mcp_clients.append(client)
                logger.info("MCP '%s': 注册 %d 个工具", server_cfg.get("name", "mcp"), len(tools))
            except Exception as e:
                logger.warning("MCP '%s' 启动失败: %s", server_cfg.get("name", "mcp"), e)

        return self._agent

    # ── 自动注册（模块扫描） ────────────────────────────

    def auto_register(self, *modules):
        """自动扫描模块中的组件并注册。

        支持自动发现的组件类型:
          - @tool 函数 → 累加注册到 Agent
          - SkillBase 子类 → 累加注册到 Agent
          - MemoryInterface 实现类 → 替换默认记忆
          - LLMClient 实现类 → 替换默认 LLM

        用法:
            import tools, skills, memory, llm

            app = AgentCore()
            app.auto_register(tools, skills, memory, llm)
        """
        for mod in modules:
            for name, obj in inspect.getmembers(mod):
                # ── 工具 ──────────────────────────────
                if isinstance(obj, _ToolWrapper) and obj not in self._builtin_tools:
                    self._builtin_tools.append(obj)
                    if self._agent is not None:
                        self._agent.add_tool(obj)
                    continue

                if not inspect.isclass(obj):
                    continue

                # ── 技能 ──────────────────────────────
                if issubclass(obj, SkillBase) and obj is not SkillBase:
                    instance = obj()
                    if not hasattr(self, "_builtin_skills"):
                        self._builtin_skills = []
                    self._builtin_skills.append(instance)
                    if self._agent is not None:
                        self._agent.add_skill(instance)
                    continue

                # ── 记忆 (替换默认) ────────────────────
                if self._memory is None and issubclass(obj, MemoryInterface) and obj is not MemoryInterface:
                    try:
                        self._memory = obj()
                        logger.info("auto_register: 使用 %s", obj.__name__)
                    except Exception as e:
                        logger.debug("跳过 %s (实例化失败: %s)", obj.__name__, e)

                # ── LLM (替换默认) ─────────────────────
                if self._detected_llm is None and issubclass(obj, LLMClient) and obj is not LLMClient:
                    try:
                        self._detected_llm = obj()
                        logger.info("auto_register: 使用 %s", obj.__name__)
                    except Exception as e:
                        logger.debug("跳过 %s (实例化失败: %s)", obj.__name__, e)

    # ── 装饰器 ────────────────────────────────────────

    def tool(self, func=None):
        """注册工具装饰器。同时装饰和注册。"""
        if func is None:
            return lambda f: self.tool(f)

        wrapper = _tool_decorator(func)
        self._builtin_tools.append(wrapper)

        # 如果 Agent 已构建，直接注册
        if self._agent is not None:
            self._agent.add_tool(wrapper)

        return wrapper

    def skill(self, cls=None):
        """注册技能装饰器。"""
        if cls is None:
            return lambda c: self.skill(c)
        if not isinstance(cls, type) or not issubclass(cls, SkillBase):
            raise TypeError(f"@skill 只能装饰 SkillBase 子类, 得到 {cls}")

        instance = cls()
        if not hasattr(self, "_builtin_skills"):
            self._builtin_skills = []
        self._builtin_skills.append(instance)

        # 如果 Agent 已构建，直接注册
        if self._agent is not None:
            for s in self._builtin_skills:
                self._agent.add_skill(s)

        return cls

    # ── 运行入口 ──────────────────────────────────────

    def run(
        self,
        query: str = "",
        *,
        session_id: str = "",
        interactive: bool = True,
        host: str = "",
        port: int = 0,
    ):
        """启动应用。

        参数:
            query: 单次提问内容（提供时自动进入 ask 模式）
            session_id: 会话 ID（留空则使用配置文件中的值）
            interactive: 是否交互式（默认 True，被 query 覆盖）
            host: 健康检查服务监听地址
            port: 健康检查服务端口
        """
        agent = self._build()

        if not agent._llm:
            logger.error("LLM 客户端未配置，请设置 API Key 或提供配置文件")
            sys.exit(1)

        if not self._config["api_key"]:
            logger.warning("未设置 API Key，请设置 OPENAI_API_KEY 环境变量或传入 api_key")

        # session_id: 参数 > 配置文件 > 默认值
        sid = session_id or self._config.get("session_id", "default")

        # 确定运行模式
        if query:
            return self._run_ask(agent, query, session_id=sid)
        if host and port:
            return self._run_serve(agent, host, port)
        if interactive:
            return self._run_interactive(agent, session_id=sid)

        # 默认交互模式
        return self._run_interactive(agent, session_id=sid)

    # ── 交互模式 ──────────────────────────────────────

    def _run_interactive(self, agent: Agent, session_id: str = "default"):
        """交互式对话。"""
        cancel_event = Event()
        current_sid = session_id

        def _signal_handler(sig, frame):
            print("\n[正在取消...]")
            cancel_event.set()

        signal.signal(signal.SIGINT, _signal_handler)

        print()
        print("=" * 56)
        print(f"  AgentCore V3 — 交互式对话  ({self._name})")
        print("=" * 56)
        print(f"  Session: {current_sid}  |  命令: exit/quit 退出 | clear 清屏")
        print(f"  /session <id> 切换对话 | /log 查看日志")
        print()

        while True:
            try:
                text = input(">>> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见！")
                break

            if not text:
                continue
            if text.lower() in ("exit", "quit"):
                print("再见！")
                break
            if text.lower() == "clear":
                os.system("cls" if os.name == "nt" else "clear")
                continue
            if text.lower() == "/log":
                print(f"  {os.path.abspath(self._log_path)}")
                continue
            if text.lower().startswith("/session "):
                current_sid = text.split(" ", 1)[1].strip()
                print(f"  切换到 Session: {current_sid}\n")
                continue

            try:
                result = agent.chat(text, cancel_event=cancel_event, session_id=current_sid)
                print(f"\n{result}\n")
            except Exception as e:
                print(f"\n[错误] {e}\n")
            finally:
                cancel_event.clear()

        agent.shutdown()
        self.shutdown()

    # ── 单次提问模式 ──────────────────────────────────

    def _run_ask(self, agent: Agent, query: str, session_id: str = "default"):
        """单次提问。"""
        try:
            result = agent.chat(query, session_id=session_id)
            print(result)
            return result
        finally:
            agent.shutdown()
            self.shutdown()

    # ── 健康检查模式 ──────────────────────────────────

    def _run_serve(self, agent: Agent, host: str, port: int):
        """启动健康检查服务。"""
        from agentcore.contrib.http_server.health_server import serve_health
        try:
            serve_health(agent, host=host, port=port)
        finally:
            agent.shutdown()
            self.shutdown()

    # ── 检查点管理 ────────────────────────────────────

    @property
    def checkpointer(self) -> BaseCheckpointer:
        """获取当前检查点实例。"""
        return self._checkpointer

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """列出所有检查点摘要。"""
        sessions = self._checkpointer.list_sessions()
        result = []
        for sid in sessions:
            ckpt = self._checkpointer.load(sid)
            if ckpt:
                result.append({
                    "session_id": sid,
                    "status": ckpt.get("status"),
                    "step": ckpt.get("step"),
                    "max_steps": ckpt.get("max_steps"),
                })
        return result

    def clear_checkpoint(self, session_id: str) -> None:
        """清除指定 session 的检查点。"""
        self._checkpointer.delete(session_id)

    def shutdown(self) -> None:
        """释放资源，包括关闭 MCP Server 连接。"""
        for client in getattr(self, "_mcp_clients", []):
            try:
                client.close()
            except Exception:
                pass
        self._mcp_clients = []

    # ── 属性 ──────────────────────────────────────────

    @property
    def agent(self) -> Agent:
        """获取内部 Agent 实例（延迟构建）。"""
        return self._build()
