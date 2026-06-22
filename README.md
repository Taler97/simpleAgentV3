# AgentCore V3

一个 AI Agent 运行框架，提供装饰器风格的 `@tool` / `@skill`，可快速为 LLM 接入工具调用、对话记忆和可观测性。

---

## 目录

- [简介](#简介)
- [安装](#安装)
- [快速上手](#快速上手)
  - [10 分钟示例](#10-分钟示例)
  - [启动应用](#启动应用)
- [开发指南](#开发指南)
  - [定义工具 — @tool](#定义-tool)
  - [定义技能 — @skill](#定义-skill)
  - [模块自动注册 — auto_register](#模块自动注册-auto_register)
  - [直接使用 Agent API](#直接使用-agent-api)
  - [事件监听](#事件监听)
  - [超时与取消](#超时与取消)
- [记忆](#记忆)
- [检查点](#检查点)
- [配置](#配置)
- [项目结构](#项目结构)
- [部署](#部署)

---

## 简介

AgentCore V3 的核心是一个 **ReAct（推理-行动-观察）循环**。它让 LLM 可以反复思考问题、调用工具获取信息，最终给出答案。

框架帮你处理了四件事：

- **工具注册**：加一行 `@tool` 装饰器，函数自动变成 Agent 可调用的工具
- **JSON 解析容错**：LLM 输出格式不完美时自动修复
- **执行安全**：每个 LLM 调用和工具执行都有超时保护，支持 Ctrl+C 取消
- **可观测性**：每步推理记录自动输出到 JSONL 日志文件

同步模型（无 asyncio），用线程池处理并发，调试简单。

---

## 安装

```bash
pip install -r requirements.txt

# 如需 OpenAI
pip install openai>=1.0
```

---

## 快速上手

### 10 分钟示例

创建一个文件 `run.py`：

```python
from agentcore import AgentCore

app = AgentCore(api_key="sk-xxx", model="gpt-4o")

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

启动：

```bash
python run.py
```

进入交互模式，输入问题即可：

```
>>> 北京的天气怎么样？

正在调用工具 get_weather("city": "北京")...
北京: 25°C, 晴

>>> 123\* 456 等于多少？

正在调用工具 calculator("expression": "123\*456")...
56088
```

LLM 会自动判断何时调用哪个工具，无需你手动编排。

### 启动应用

项目已有 `main.py`，可直接使用：

```bash
# 交互式对话
python main.py

# 单次提问
python main.py "1+1等于几？"

# 查看帮助
python main.py --help
```

`main.py` 会自动导入 `tools/tools.py` 中定义的三个工具（calculator、now、echo）并注册到 Agent。

---

## 开发指南

### 定义工具 — @tool {#定义-tool}

`@tool` 装饰器把一个普通函数变成 Agent 可调用的工具。函数的参数名和类型注解会自动生成 JSON Schema，不需要手写。

```python
from agentcore import AgentCore

app = AgentCore(api_key="sk-xxx")

@app.tool
def fetch_news(category: str, limit: int = 5) -> str:
    """获取新闻头条"""
    # 调用新闻 API...
    return f"取得 {limit} 条 {category} 新闻"

@app.tool
def send_email(to: str, subject: str, body: str) -> str:
    """发送邮件"""
    # 调用邮件服务...
    return f"邮件已发送至 {to}"
```

工具函数应当：
- 有清晰的函数名和 docstring（LLM 靠它们决定何时调用）
- 参数有类型注解（自动转为 JSON Schema）
- 执行时间尽量短（LLM 在等结果）
- 是纯函数，不要在工具内部调用 `agent.chat()`

如果不用 `app.tool` 装饰器，也可以用 `tools/tools.py` 的方式单独定义后通过 `auto_register` 注册（见下文）。

### 定义技能 — @skill {#定义-skill}

技能是**多步骤工作流**，适合代码审查、报告生成、多步数据查询等场景。技能内部可以多次调用 `agent.chat()`。

```python
from agentcore.adapters.skill import SkillBase
from agentcore.adapters.decorators import skill

@skill
class ReportSkill(SkillBase):
    name = "report"
    description = "生成数据分析报告"

    def run(self, agent, user_input: str) -> str:
        # 步骤 1: 理解需求
        requirements = agent.chat(f"提取报告需求: {user_input}")

        # 步骤 2: 查询数据（Agent 会使用已注册的工具）
        data = agent.chat(f"根据需求查询数据: {requirements}")

        # 步骤 3: 生成报告
        return agent.chat(f"基于数据生成报告: {data}")
```

使用技能：在对话中说出技能名称即可触发。

```
>>> report 分析上个月的销售数据
```

注意：`@tool` 和 `@skill` 的区别——**工具是原子的**，输入→输出，内部不能调 `agent.chat()`；**技能是编排的**，内部可以多次调 `agent.chat()` 来完成多步骤任务。

### 模块自动注册 — auto_register

把工具和技能集中写在模块里，批量注册：

```python
import tools      # tools.py 里有 @tool 函数
import skills     # skills.py 里有 @skill 类

app = AgentCore(api_key="sk-xxx")
app.auto_register(tools, skills)
```

`auto_register` 会扫描模块，自动发现：

| 写法 | 自动变成 |
|---|---|
| `@tool def f():` | 工具 |
| `class X(SkillBase):` | 技能 |
| `class X(MemoryInterface):` | 替换默认记忆 |
| `class X(LLMClient):` | 替换默认 LLM |

传给 `auto_register` 的可以是多个模块：

```python
app.auto_register(tools, my_custom_skills)
```

### 直接使用 Agent API

不经过 `AgentCore`，直接操作 Agent：

```python
from agentcore.adapters.agent import Agent
from agentcore.services.llm.openai_sdk import OpenAILLM
from agentcore.adapters.decorators import tool

@tool
def echo(text: str) -> str:
    return text

agent = Agent(
    llm=OpenAILLM(api_key="sk-xxx"),
)
agent.add_tool(echo)

result = agent.chat("你好")
print(result)
```

不加 `session_id` 时默认同一个 session 对话，Agent 会记住上下文。传入不同 `session_id` 隔离不同会话。

### 事件监听

每步推理执行会产出一个 `StepRecord`，里面记录了 thought、action、action_input、observation 等完整链路。可以通过监听器做自定义处理：

```python
def log_to_db(record):
    """把每步记录写入数据库"""
    print(f"[{record.step}] {record.action} → {record.observation[:50]}...")

agent.add_listener("db_logger", log_to_db)
```

内置的 JSONL 文件日志也是通过这个机制实现的。

### 超时与取消

长时间运行的对话可以设置超时，也可以在另一个线程发取消信号：

```python
from threading import Event

cancel = Event()

# 另一个线程中执行 cancel.set() 即可中断
result = app.chat(
    "一个比较耗时的任务",
    llm_timeout=30.0,    # LLM 调用超时（秒）
    tool_timeout=15.0,   # 工具执行超时（秒）
    max_steps=10,         # 最大推理步数
    cancel_event=cancel,
)
```

交互模式下按下 Ctrl+C 会自动发取消信号。

---

## 记忆

默认使用滑动窗口记忆（内存），按 `session_id` 保留最近 N 轮对话。窗口外的旧消息会被丢弃。

```python
# 调整窗口大小
app = AgentCore(window_size=20)

# 使用 Redis 持久化记忆
from agentcore.services.memory.redis_memory import RedisMemory
app = AgentCore(memory=RedisMemory(host="localhost", port=6379))
```

记忆（Memory）和下一节的检查点（Checkpoint）不同：
- **Memory**：存对话历史，每次 chat 都会读历史做上下文
- **Checkpoint**：存执行中间状态，进程崩溃后可恢复

---

## 检查点

当 Agent 执行多步骤任务时（例如调用了多次工具），进程可能崩溃。检查点机制把每一轮的执行状态保存到文件，重启后可以从断点继续。

```python
# 默认启用，检查点存在 .checkpoints/ 目录
app = AgentCore(checkpoint_dir=".checkpoints")

# 查看有哪些检查点
app.list_checkpoints()
# 输出：[{"session_id": "default", "status": "in_progress", "step": 3, "max_steps": 10}]

# 崩溃后从断点恢复
result = app.agent.resume(session_id="default")

# 清除检查点
app.clear_checkpoint(session_id="default")
```

---

## 配置

三种方式（优先级从上到下）：

1. **代码传参** — `AgentCore(api_key="sk-xxx", model="gpt-4o")`
2. **环境变量** — `set OPENAI_API_KEY=sk-xxx`（Windows）或 `export OPENAI_API_KEY=sk-xxx`（Linux/Mac）
3. **配置文件** — 编辑 `resources/config.yaml`

```yaml
# resources/config.yaml
llm:
  model: "gpt-4o"
  api_key: "sk-xxx"
  base_url: ""           # 兼容 OpenAI 格式的代理地址
  temperature: 0.7
  max_tokens: 4096

memory:
  window_size: 10

runtime:
  pool_size: 4

log_path: logs/agentcore.jsonl
```

如果同时使用了多种方式，显式传参覆盖环境变量，环境变量覆盖配置文件。

---

## 项目结构

```
├── main.py                     # 启动入口
├── tools/tools.py              # 内置工具集（calculator, now, echo）
├── resources/config.yaml       # 配置文件
├── Dockerfile                  # 容器部署
├── pyproject.toml              # 项目元信息
├── requirements.txt            # Python 依赖
│
└── agentcore/                  # 核心库
    ├── __init__.py             # 导出 AgentCore
    ├── app.py                  # AgentCore 启动器
    │
    ├── core/                   # 核心引擎（可独立使用）
    │   ├── interfaces.py       # 抽象接口定义
    │   ├── orchestrator.py     # ReAct 推理循环
    │   ├── parser.py           # JSON 容错解析
    │   └── tool_manager.py     # 工具注册与执行
    │
    ├── runtime/                # 运行时组件
    │   ├── runner.py           # 同步运行器
    │   ├── waiter.py           # 线程池执行守卫
    │   ├── broadcaster.py      # 事件分发
    │   └── checkpointer.py     # 检查点
    │
    ├── adapters/               # 适配层
    │   ├── agent.py            # Agent 封装
    │   ├── builder.py          # 从 YAML 构建 Agent
    │   ├── cli.py              # 命令行入口
    │   ├── decorators.py       # @tool / @skill 装饰器
    │   └── skill.py            # SkillBase 基类
    │
    ├── services/               # 服务实现
    │   ├── llm/
    │   │   ├── openai_sdk.py   # OpenAI SDK 客户端
    │   │   └── http_client.py  # HTTP 客户端
    │   ├── memory/
    │   │   ├── sliding_window.py  # 滑动窗口记忆
    │   │   └── redis_memory.py    # Redis 持久化记忆
    │   ├── tools/
    │   │   ├── calculator_tool.py # 计算器工具
    │   │   └── datetime_tool.py   # 日期时间工具
    │   └── logger/
    │       └── file_logger.py     # JSONL 文件日志
    │
    ├── tests/                  # 测试
    │   ├── unit/               # 单元测试
    │   ├── integration/        # 集成测试
    │   └── chaos/              # 混沌测试
    │
    └── examples/               # 示例
        ├── quick_start.py
        └── code_review_skill.py
```

### 执行流程

```
用户输入
    │
    ▼
AgentCore 启动 → Agent.chat()
                    │
                    ├─ 技能触发? → 执行技能（可再次调 chat）
                    │
                    └─ SyncRunner → Orchestrator (ReAct 循环)
                                      │
                                      ├─ ① LLM 推理
                                      ├─ ② JSON 解析
                                      ├─ ③ 执行工具
                                      ├─ ④ 保存检查点
                                      └─ ⑤ 广播事件
                                            │
                                            ▼
                                      FileLogger 写 JSONL
```

---

## 部署

### Docker

```bash
docker build -t agentcore .
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=sk-xxx \
  -v ./logs:/app/logs \
  agentcore
```

健康检查：`GET /health`

### 水平扩展

Agent 实例不保存状态（状态存于 Redis 或检查点文件），可以多实例部署：

```
        负载均衡
         /    \
    Agent1   Agent2
         \    /
         Redis (会话状态)
```
