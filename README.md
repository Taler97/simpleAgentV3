# AgentCore V3

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
