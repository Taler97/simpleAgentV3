# AgentCore V3 — 同步 · 可插拔 · ReAct Agent 框架

一个**同步模型**的 AI Agent 运行框架。核心是一个 **ReAct（推理-行动-观察）循环**，让 LLM 可以反复思考、调用工具、观察结果，最终给出答案。

---

## 设计理念

### 同步模型，拒绝复杂性

没有 asyncio，没有事件循环，没有协程。用线程池处理并发，所有的执行路径都是线性的——这意味着你可以在一条 `print` 语句里看清完整的调用链。调试体验与写普通 Python 脚本无异。

### 可插拔架构

LLM、记忆存储、日志——所有组件都遵循 Protocol 协议接口。框架不绑定任何具体实现，替换实现不需要改框架代码。

```
AgentCore → Agent → Orchestrator (ReAct 循环)
                      ├─ LLM (OpenAI / DeepSeek / 自定义)
                      ├─ Memory (滑动窗口 / Redis / 自定义)
                      ├─ Tools (@tool 装饰器 / MCP 协议)
                      └─ Logger (JSONL 文件 / 自定义监听器)
```

### 安全是默认配置

- 计算器用 AST 白名单求值，不是 `eval()`
- 每次 LLM 调用和工具执行都有独立超时守卫
- 支持 `Ctrl+C` 优雅取消
- 循环检测防止 Agent 死循环

### 最小惊喜原则

一行 `@tool` 装饰器，函数自动变成 Agent 可调用的工具。不加魔法，不改函数签名，不要求继承特定基类。框架只是基础设施，你的业务逻辑保持干净。

---

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 配置

编辑 [resources/config.yaml](file:///resources/config.yaml)，填入你的 LLM API Key：

```yaml
llm:
  model: "gpt-4o"
  api_key: "sk-xxx"              # 替换为你的 key
  base_url: ""                   # 兼容 OpenAI 格式的代理地址
```

支持 OpenAI、DeepSeek 等兼容 OpenAI API 格式的服务商。

### 启动

```bash
# 交互式对话
python -m agentcore.adapters.cli

# 单次提问
python -m agentcore.adapters.cli "1+1等于几？"

# 指定配置文件
python -m agentcore.adapters.cli -c resources/config.yaml
```

进入交互模式后：

```
>>> 现在几点了？

>>> 123 * 456 等于多少？
```

LLM 会自动调用已注册的工具来回答。

### 注册为 CLI 命令

```bash
pip install -e .
agentcore                    # 交互模式
agentcore "你好"             # 单次提问
```

---

## 五分钟上手

创建一个文件 `run.py`：

```python
from agentcore import AgentCore

app = AgentCore(api_key="sk-xxx")

@app.tool
def get_weather(city: str) -> str:
    """获取指定城市的天气"""
    return f"{city}: 25°C, 晴"

@app.tool
def calculator(expression: str) -> str:
    """计算数学表达式"""
    import ast
    tree = ast.parse(expression.strip(), mode="eval")
    return str(eval(compile(tree, "", "eval")))

if __name__ == "__main__":
    app.run()
```

```bash
python run.py
```

---

## 核心概念

### 工具（Tool）— `@tool`

工具是原子操作，输入 → 输出，内部**不能**调用 `agent.chat()`。

```python
@app.tool
def fetch_news(category: str, limit: int = 5) -> str:
    """获取新闻头条"""
    return f"取得 {limit} 条 {category} 新闻"
```

函数名、docstring、参数类型注解自动生成 JSON Schema，LLM 据此决定调用哪个工具。

### 技能（Skill）— `@skill`

技能是多步工作流，内部可以多次调用 `agent.chat()` 编排复杂任务。

```python
from agentcore.adapters.skill import SkillBase
from agentcore.adapters.decorators import skill

@skill
class ReportSkill(SkillBase):
    name = "report"
    description = "生成数据分析报告"

    def run(self, agent, user_input: str) -> str:
        req = agent.chat(f"提取报告需求: {user_input}")
        data = agent.chat(f"根据需求查询数据: {req}")
        return agent.chat(f"基于数据生成报告: {data}")
```

在对话中提及技能名称即可触发。

### 模块自动注册

工具和技能可以集中写在模块里，批量扫描注册：

```python
app.auto_register(tools_module, skills_module)
```

`auto_register` 自动发现 `@tool` 函数、`SkillBase` 子类，以及自定义的 `LLMClient` 和 `MemoryInterface` 实现。

---

## 架构

### 项目结构

```
agentcore/
├── __init__.py           # 导出 AgentCore
├── app.py                # 启动器（装饰器、生命周期管理）
├── mcp.py                # MCP 客户端（STDIO 传输）
│
├── core/                 # 核心引擎
│   ├── interfaces.py     # 抽象接口定义
│   ├── orchestrator.py   # ReAct 推理循环
│   ├── parser.py         # JSON 容错解析
│   └── tool_manager.py   # 工具注册与执行
│
├── runtime/              # 运行时组件
│   ├── runner.py         # 生成器驱动
│   ├── waiter.py         # 线程池守卫（超时/取消）
│   ├── checkpointer.py   # 检查点（崩溃恢复）
│   └── broadcaster.py    # 事件分发
│
├── adapters/             # 适配层
│   ├── agent.py          # Agent 封装（.chat() 入口）
│   ├── cli.py            # 命令行入口
│   ├── decorators.py     # @tool / @skill 装饰器
│   └── skill.py          # SkillBase 基类
│
└── services/             # 服务实现
    ├── llm/openai_sdk.py       # OpenAI SDK 客户端
    ├── memory/
    │   ├── sliding_window.py   # 内存滑动窗口（默认）
    │   └── redis_memory.py     # Redis 持久化
    ├── tools/
    │   ├── calculator_tool.py  # 安全计算器（AST 求值）
    │   └── datetime_tool.py    # 日期时间
    └── logger/file_logger.py   # JSONL 日志
```

### 执行流程

```
用户输入
    │
    ▼
AgentCore.run()
    │
    ▼
Agent.chat()
    ├─ 技能匹配? → 执行技能（可多次调 chat()）
    │
    └─ SyncRunner → Orchestrator.run()  (ReAct 循环)
                      │
                      ├─ ① LLM.generate(messages)
                      ├─ ② Parser.parse() 容错解析 JSON
                      ├─ ③ action=""? → 返回最终答案
                      ├─ ④ ToolManager.execute() 执行工具
                      ├─ ⑤ 观察结果加入 messages，继续循环
                      ├─ ⑥ 循环检测（防止死循环）
                      └─ ⑦ FileCheckpointer 保存中间状态
                            │
                            ▼
                      Broadcaster → FileLogger 写 JSONL
```

---

## 功能特性

### JSON 容错解析

Parser 自动修复 LLM 常见的 JSON 格式问题：单引号代替双引号、多余尾部逗号、markdown 代码块包裹、行注释等。

### 超时与取消

每次 LLM 调用和工具执行都有独立超时保护，支持 `Ctrl+C` 取消：

```python
from threading import Event

cancel = Event()
result = app.agent.chat(
    "耗时任务",
    llm_timeout=30.0,
    tool_timeout=15.0,
    max_steps=10,
    cancel_event=cancel,
)
```

### 检查点恢复

多步执行中间崩溃后，可从断点继续：

```python
# 列出检查点
app.list_checkpoints()

# 恢复执行
result = app.agent.resume(session_id="default")

# 清除
app.clear_checkpoint(session_id="default")
```

### 事件监听

每步推理产出 `StepRecord`，包含 thought、action、action_input、observation 等完整链路：

```python
def my_listener(record):
    print(f"[{record.step}] {record.action} -> {record.observation[:50]}")

agent.add_listener("my_logger", my_listener)
```

内置 JSONL 文件日志也是通过此机制实现。

### MCP 协议支持

通过 STDIO 启动 MCP Server 子进程，自动注册其工具。在 [resources/config.yaml](file:///resources/config.yaml) 中配置：

```yaml
mcp_servers:
  - name: filesystem
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "."]
```

### 记忆

| 实现 | 说明 |
|------|------|
| `SlidingWindowMemory` | 内存滑动窗口，按 session_id 保留最近 N 轮对话 |
| `RedisMemory` | Redis 持久化，支持 TTL 过期 |

### 健康检查

```bash
python -m agentcore.adapters.cli --host 0.0.0.0 --port 8080
# 访问 http://localhost:8080/health
```

---

## 配置

三种配置方式，优先级从上到下：

1. **代码传参** — `AgentCore(api_key="sk-xxx", model="gpt-4o")`
2. **环境变量** — `OPENAI_API_KEY=sk-xxx`
3. **配置文件** — `resources/config.yaml`

---

## 部署

```bash
docker build -t agentcore .
docker run -p 8080:8080 -e OPENAI_API_KEY=sk-xxx agentcore
```
