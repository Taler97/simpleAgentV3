# AgentCore V3

**生产级 AI Agent 运行底座**

> 极简、声明式、生产就绪。用装饰器定义能力，让 AI Agent 开发回归简单。

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Release](https://img.shields.io/github/v/release/Taler97/simpleAgentV3)](https://github.com/Taler97/simpleAgentV3/releases)

---

## 一、设计理念

### 1.1 我们解决什么问题？

在构建基于大语言模型的 Agent 应用时，开发者普遍面临三重困境：

| 困境 | 具体表现 |
|------|----------|
| **稳定性缺失** | LLM API 超时、工具调用卡死，导致整个服务不可用 |
| **框架过重** | LangChain 等框架体量庞大，升级时经常破坏兼容性 |
| **可观测性差** | 无法追溯 Agent 的完整推理链，问题根因难以定位 |

**AgentCore V3 的答案是：用极简内核 + 声明式 API，让 Agent 开发既有优雅的编码体验，又有生产级的可靠保障。**

### 1.2 核心设计哲学

| 原则 | 说明 |
|------|------|
| **内核永久锁定** | `core/` + `runtime/` 代码量 **≤500 行**，永不因业务需求变更 |
| **声明式优于命令式** | 用 `@tool` / `@skill` 装饰器定义能力，框架自动完成注册与调度 |
| **可观测性是一等公民** | 每一步执行自动产出结构化事件，日志、监控、追踪开箱即用 |
| **无 asyncio 依赖** | 采用**同步主循环 + 线程池**模型，调试简单，无事件循环冲突 |
| **可插拔一切** | LLM、记忆、日志、工具全部通过接口注入，替换实现无需改内核 |

### 1.3 与同类框架的对比

| 维度 | AgentCore V3 | LangChain | 自研脚本 |
|------|--------------|-----------|----------|
| 核心代码量 | **≤500 行** | 数万行 | 无标准 |
| 学习曲线 | **极低**（5 分钟上手） | 陡峭 | 无 |
| 超时/取消控制 | **原生支持** | 需自行实现 | 需自行实现 |
| 声明式 API | **✅ @tool / @skill** | 部分支持 | 无 |
| 可观测性 | **原生事件流 + JSONL** | Callback 机制 | 靠 print |
| 版本兼容性 | **内核永久锁定** | 升级常破坏 API | 无 |

---

## 二、风格特点

### 2.1 声明式编程：用装饰器定义能力

AgentCore V3 的最大特点是 **“用装饰器驱动开发”**。你只需在函数上添加一行装饰器，框架自动完成工具注册、参数解析和调用调度：

```python
from agentcore import AgentCore

app = AgentCore(api_key="sk-xxx")

@app.tool
def get_weather(city: str) -> str:
    """获取指定城市的天气"""
    return f"{city}: 25°C，晴"

@app.tool
def calculator(expression: str) -> str:
    """计算数学表达式"""
    return str(eval(expression))

if __name__ == "__main__":
    app.run()
```

- **`@app.tool`**：任何函数加一行装饰器，即成为 Agent 可调用的工具
- **函数签名 + 类型注解**：自动转换为 JSON Schema，零额外配置
- **`app.run()`**：一行命令进入交互式对话，无需编写 CLI 逻辑

### 2.2 技能（Skill）：宏观流程编排器

工具是**原子操作**，技能是**宏观流程编排器**。技能内部可以多次调用 `agent.chat()`，实现多步骤工作流：

```python
from agentcore.adapters.skill import SkillBase
from agentcore.adapters.decorators import skill

@skill
class CodeReviewSkill(SkillBase):
    name = "code_review"
    description = "审查代码变更，生成审查报告"

    def run(self, agent, user_input: str) -> str:
        # 步骤 1: 提取 PR 信息
        pr_info = agent.chat(f"从以下输入中提取 PR 信息: {user_input}")
        # 步骤 2: 审查代码
        analysis = agent.chat(f"请审查以下代码变更:\n{diff}")
        # 步骤 3: 生成最终报告
        return f"## 审查报告\n\n{pr_info}\n\n{analysis}"
```

**关键约束**：工具是原子操作（输入→输出），**禁止在工具内部调用 `agent.chat()`**；技能是宏观编排器，**可以多次调用 `agent.chat()`**。职责清晰，互不污染。

### 2.3 自动注册（auto_register）：零配置模块发现

AgentCore V3 支持模块级别的自动发现，无需逐个导入工具或技能：

```python
app = AgentCore(api_key="sk-xxx")

# 扫描并注册 tools/ 和 skills/ 目录下的所有实现
app.auto_register("tools", "skills")
app.run()
```

**工作原理**：`auto_register` 会递归扫描指定模块，自动发现所有继承自 `ToolBase` 或 `SkillBase` 的类，并完成实例化和注册。你只需按约定将代码放在对应目录下，框架帮你做剩下的。

### 2.4 可插拔一切：接口注入

所有业务能力通过**接口注入**的方式接入内核：

```python
from agentcore.services.llm.openai_sdk import OpenAILLM
from agentcore.services.memory.redis_memory import RedisMemory
from agentcore.services.logger.file_logger import FileLogger

app = AgentCore(
    llm=OpenAILLM(api_key="sk-xxx", model="gpt-4o"),
    memory=RedisMemory(redis_url="redis://localhost:6379"),
    logger=FileLogger("logs/agent.jsonl"),
)
```

**内置实现**：
- **LLM**：OpenAI SDK、纯 HTTP
- **Memory**：滑动窗口、Redis 分布式
- **Logger**：JSONL 文件、自定义监听器

你可以自由替换任意实现，内核代码一行不改。

### 2.5 原生超时与取消控制

所有 LLM 调用和工具执行都有超时兜底：

```python
result = app.chat(
    "复杂问题",
    llm_timeout=30.0,    # LLM 调用超时
    tool_timeout=15.0,   # 工具执行超时
    max_steps=10,        # 最大推理步数
)
```

支持取消信号，适合长任务中断场景：

```python
from threading import Event

cancel = Event()
# 在另一个线程中: cancel.set()
result = app.chat("长时间任务", cancel_event=cancel)
```

### 2.6 原生可观测性：事件流 + JSONL

每一步执行自动产出 `StepRecord`，包含完整的推理链：

```python
record = StepRecord(
    step=1,
    thought="用户想知道北京天气，我应该调用天气工具",
    action="get_weather",
    action_input='{"city": "北京"}',
    observation="北京: 25°C，晴",
    trace_id="a1b2c3d4",
    timestamp="2024-01-15T10:30:00",
)
```

所有记录自动写入 JSONL 日志文件，便于后续审计和分析。你也可以通过 `add_listener` 注册自定义监听器，实时处理事件流。

---

## 三、快速开始

### 3.1 安装

```bash
pip install -e .

# 如需全部可选依赖
pip install -e ".[all]"
```

### 3.2 基础示例

```python
from agentcore import AgentCore

app = AgentCore(api_key="sk-xxx")

@app.tool
def get_weather(city: str) -> str:
    """获取指定城市的天气"""
    return f"{city}: 25°C，晴"

@app.tool
def calculator(expression: str) -> str:
    """计算数学表达式"""
    return str(eval(expression))

if __name__ == "__main__":
    app.run()
```

### 3.3 部署

```bash
# 构建镜像
docker build -t agentcore-v3 .

# 运行容器
docker run -d -p 8080:8080 \
    -e LLM_API_KEY="sk-xxx" \
    -v ./logs:/app/logs \
    --name agentcore \
    agentcore-v3
```

健康检查端点：`GET /health`

---

## 四、项目约束

| 指标 | 目标 | 当前 |
|------|------|------|
| 内核代码量 (`core/` + `runtime/`) | ≤ 500 行 | ✅ |
| 全项目代码量（不含测试/示例） | ≤ 1500 行 | ✅ |
| 核心模块测试覆盖率 | ≥ 80% | ✅ |
| 超时精度 | ±0.5s | 0.5s 脉冲检查 |
| 异步模型 | 线程池，无 asyncio | ✅ |

---

## 五、贡献

欢迎提交 Issue 和 Pull Request。

1. Fork 本仓库
2. 创建你的功能分支 (`git checkout -b feature/amazing`)
3. 提交你的改动 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing`)
5. 创建 Pull Request

---

## 六、许可证

MIT License

Copyright (c) 2024 Taler97# AgentCore V3

生产级 AI Agent 运行底座。提供 SpringBoot 风格的声明式 `@tool` / `@skill` 装饰器，5 分钟搭建一个具备工具调用、记忆、可观测性的 LLM Agent。

## 目录

- [一、快速开始](#一快速开始)
- [二、核心概念](#二核心概念)
- [三、高级用法](#三高级用法)
- [四、部署](#四部署)
- [五、架构总览](#五架构总览)

---

## 一、快速开始

### 安装

```bash
pip install -r requirements.txt
```

如果使用 OpenAI 模型，安装可选依赖：

```bash
pip install ".[openai]"
```

### 最小示例（10 行代码）

```python
# run.py
from agentcore import AgentCore

app = AgentCore(
    api_key="sk-xxx",     # 也可通过环境变量 OPENAI_API_KEY 设置
    model="gpt-4o",
)

@app.tool
def get_weather(city: str) -> str:
    """获取指定城市的天气"""
    return f"{city}: 25°C, 晴"

if __name__ == "__main__":
    app.run()  # 进入交互式对话
```

启动后：

```
>>> 北京的天气怎么样？

[Agent] 让我查询一下...

正在使用 get_weather(city="北京")...

北京: 25°C, 晴
```

### 也可以通过 main.py 启动

```bash
python main.py                        # 交互式对话
python main.py "1+1等于几？"           # 单次提问
python main.py --help                  # 查看帮助
```

### 配置方式

三种方式，优先级依次递减：

1. **代码参数**：`AgentCore(api_key="sk-xxx", model="gpt-4o")`
2. **环境变量**：`OPENAI_API_KEY=sk-xxx`
3. **配置文件**：编辑 `resources/config.yaml`

```yaml
# resources/config.yaml
llm:
  model: "gpt-4o"
  api_key: "sk-xxx"
  temperature: 0.7
  max_tokens: 4096

memory:
  window_size: 10

runtime:
  pool_size: 4
```

---

## 二、核心概念

### 2.1 工具（Tool）— `@tool`

任何函数加 `@tool` 即可成为 Agent 可调用的工具。**函数签名和类型注解自动转换为 JSON Schema**，零额外配置。

```python
from agentcore import AgentCore

app = AgentCore(api_key="sk-xxx")

@app.tool
def calculator(expression: str) -> str:
    """计算数学表达式，支持 + - * / 和括号"""
    import ast
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        # ... 安全检查
        return str(eval(compile(tree, "", "eval")))
    except Exception as e:
        return f"错误: {e}"

@app.tool
def now(format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前日期时间"""
    from datetime import datetime
    return datetime.now().strftime(format)
```

工具会被自动注册到 Agent，LLM 会根据当前问题自动选择调用的工具。

### 2.2 技能（Skill）— `@skill`

技能是**宏观流程编排器**，内部可以多次调用 `agent.chat()`，实现多步骤工作流。

```python
from agentcore import AgentCore
from agentcore.adapters.skill import SkillBase
from agentcore.adapters.decorators import skill

app = AgentCore(api_key="sk-xxx")

@skill
class CodeReviewSkill(SkillBase):
    name = "code_review"
    description = "审查代码变更，生成审查报告"

    def run(self, agent, user_input: str) -> str:
        # 步骤 1: 提取 PR 信息
        pr_info = agent.chat(f"从以下输入中提取 PR/代码变更信息: {user_input}")

        # 步骤 2: 审查代码
        analysis = agent.chat(f"请审查以下代码变更:\n{diff}")

        # 步骤 3: 生成最终报告
        return f"## 审查报告\n\n{pr_info}\n\n{analysis}"
```

触发技能只需在对话中包含技能名称：

```
>>> code_review 请审查这个 PR #1234 的改动
```

### 2.3 自动注册模块（auto_register）

可以将工具、技能、甚至自定义 LLM 或 Memory 实现在模块中定义，然后批量扫描注册：

```python
import tools     # 模块内有 @tool 函数
import skills    # 模块内有 @skill 类

app = AgentCore(api_key="sk-xxx")
app.auto_register(tools, skills)
```

`auto_register` 会自动发现：
- `@tool` 装饰的函数 → 注册为工具
- `SkillBase` 子类 → 注册为技能
- `MemoryInterface` 实现类 → 替换默认记忆
- `LLMClient` 实现类 → 替换默认 LLM

### 2.4 记忆（Memory）

默认使用**滑动窗口记忆**（内存），按 `session_id` 存储最近 N 轮对话。

```python
from agentcore import AgentCore

# 调整对话窗口大小
app = AgentCore(window_size=20)
```

如需持久化记忆，使用 Redis 实现（需安装 `redis` 依赖）：

```python
from agentcore.services.memory.redis_memory import RedisMemory

app = AgentCore(memory=RedisMemory(host="localhost", port=6379))
```

### 2.5 检查点（Checkpoint）

> 与 Memory 不同：Memory 存"对话历史"，Checkpoint 存"执行中间状态"。

当 Agent 执行多步骤任务（如多次调用工具）时，如果进程崩溃，可从断点恢复。

```python
# 默认启用，检查点存储在 .checkpoints/ 目录
app = AgentCore(checkpoint_dir=".checkpoints")

# 查看所有检查点
app.list_checkpoints()
# [{"session_id": "default", "status": "in_progress", "step": 3, "max_steps": 10}]

# 崩溃后恢复
result = app.agent.resume(session_id="default")

# 清除指定 session 的检查点
app.clear_checkpoint(session_id="default")
```

### 2.6 日志（Logging）

每步执行记录（StepRecord）自动写入 JSONL 格式日志文件。

```python
app = AgentCore(log_path="logs/agentcore.jsonl")
```

日志示例：

```jsonl
{"step": 1, "action": "calculator", "action_input": "{\"expression\": \"1+1\"}", "thought": "需要计算...", "result": "2", "_timestamp": "2026-06-20T10:30:00"}
```

---

## 三、高级用法

### 3.1 直接使用 Agent API

```python
from agentcore.adapters.agent import Agent
from agentcore.services.llm.openai_sdk import OpenAILLM
from agentcore.adapters.decorators import tool

@tool
def get_weather(city: str) -> str:
    """获取指定城市的天气"""
    return f"{city}: 25°C, 晴"

agent = Agent(
    llm=OpenAILLM(api_key="sk-xxx", model="gpt-4o"),
)
agent.add_tool(get_weather)

# 单次对话
result = agent.chat("北京的天气怎么样？")
print(result)

# 指定 session_id（可恢复历史）
result = agent.chat("上海呢？", session_id="my-session")
```

### 3.2 自定义 LLM

实现 `LLMClient` 接口即可接入任何模型：

```python
from agentcore.core.interfaces import LLMClient

class MyLocalLLM(LLMClient):
    def generate(self, messages):
        # 调用本地模型...
        return "..."

app = AgentCore(api_key="sk-xxx")
# 通过 auto_register 自动发现
```

### 3.3 自定义记忆

实现 `MemoryInterface` 接口：

```python
from agentcore.core.interfaces import MemoryInterface

class PostgreSQLMemory(MemoryInterface):
    def save(self, record):
        # 写入 PostgreSQL

    def get_context(self, session_id):
        # 从 PostgreSQL 查询历史

    def clear(self):
        # 清空
```

### 3.4 事件监听（可观测性扩展）

Agent 每步执行产生 `StepRecord`，可以注册监听器做自定义处理：

```python
def my_monitor(record):
    print(f"[Step {record.step}] {record.action} → {record.observation}")

agent.add_listener("monitor", my_monitor)
```

内置的 JSONL 日志就是通过这个机制实现的。

### 3.5 超时与取消

长耗时任务可以设置超时，或通过 Ctrl+C 取消：

```python
result = agent.chat(
    "一个耗时任务...",
    llm_timeout=30.0,    # LLM 调用超时（秒）
    tool_timeout=15.0,   # 工具调用超时（秒）
)
```

---

## 四、部署

### Docker 部署

```bash
docker build -t agentcore .
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=sk-xxx \
  agentcore
```

Docker 镜像默认启动健康检查服务（端口 8080），可通过以下端点监测：

| 端点 | 说明 |
|---|---|
| `/health` | Agent 存活检查 |

### 水平扩展

Agent 无状态（状态存于 Redis / 检查点文件），可多实例部署：

```
         Load Balancer
         /     |     \
    Agent1  Agent2  Agent3
         \     |     /
           Redis (session 状态)
```

---

## 五、架构总览

```
用户输入
    │
    ▼
AgentCore (SpringBoot 风格启动器)
    │
    ▼
Agent.chat()
    │
    ├─ 技能触发？──→ SkillBase.run()
    │
    └─ SyncRunner.run()
            │
            ▼
    Orchestrator (ReAct 循环)
            │
            ├─ LLM 推理 ─────────→ LLMClient.generate()
            ├─ JSON 解析 ─────────→ Parser.parse()
            ├─ 工具执行 ─────────→ ToolManager.execute()
            ├─ 检查点保存 ───────→ Checkpointer.save()
            └─ 事件广播 ─────────→ Broadcaster.publish()
                    │
                    ▼
              FileLogger (JSONL)
```

### 层说明

| 层 | 目录 | 职责 |
|---|---|---|
| **Core** | `core/` | 接口定义、ReAct 循环引擎、JSON 解析、工具管理 |
| **Runtime** | `runtime/` | 线程池执行守卫、事件分发、检查点、运行器 |
| **Adapters** | `adapters/` | Agent 封装、装饰器系统、技能基类、CLI 入口 |
| **Services** | `services/` | LLM 客户端、记忆存储、工具实现、文件日志 |
| **Contrib** | `contrib/` | 健康检查 HTTP 服务 |
