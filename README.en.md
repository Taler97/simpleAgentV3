# AgentCore V3

An AI Agent runtime framework. Use `@tool` / `@skill` decorators to quickly equip LLMs with tool calling, conversational memory, and observability.

---

## Table of Contents

- [Introduction](#introduction)
- [Installation](#installation)
- [Quick Start](#quick-start)
  - [10-Minute Example](#10-minute-example)
  - [Running the App](#running-the-app)
- [Development Guide](#development-guide)
  - [Defining Tools — @tool](#defining-tool)
  - [Defining Skills — @skill](#defining-skill)
  - [Auto Registration — auto_register](#auto-registration-auto_register)
  - [Using the Agent API Directly](#using-the-agent-api-directly)
  - [Event Listeners](#event-listeners)
  - [Timeout & Cancellation](#timeout-cancellation)
- [Memory](#memory)
- [Checkpoints](#checkpoints)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Deployment](#deployment)

---

## Introduction

AgentCore V3 is built around a **ReAct (Reasoning-Action-Observation) loop**. It enables an LLM to iteratively reason about a problem, invoke tools, observe results, and produce a final answer.

The framework handles four things for you:

- **Tool registration**: add `@tool` to a function and it becomes callable by the Agent
- **Fault-tolerant JSON parsing**: fixes common formatting issues in LLM output
- **Execution safety**: every LLM call and tool execution has a timeout guard; supports Ctrl+C cancellation
- **Observability**: every reasoning step is automatically logged to a JSONL file

Synchronous threading model (no asyncio) — easy to debug and reason about.

---

## Installation

```bash
pip install -r requirements.txt

# For OpenAI support
pip install openai>=1.0
```

---

## Quick Start

### 10-Minute Example

Create `run.py`:

```python
from agentcore import AgentCore

app = AgentCore(api_key="sk-xxx", model="gpt-4o")

@app.tool
def get_weather(city: str) -> str:
    """Get the weather for a city"""
    return f"{city}: 25°C, Sunny"

@app.tool
def calculator(expression: str) -> str:
    """Evaluate a math expression"""
    import ast
    tree = ast.parse(expression.strip(), mode="eval")
    return str(eval(compile(tree, "", "eval")))

if __name__ == "__main__":
    app.run()
```

Run it:

```bash
python run.py
```

You'll enter an interactive chat:

```
>>> What's the weather in Beijing?

Calling tool get_weather("city": "Beijing")...
Beijing: 25°C, Sunny

>>> What is 123 * 456?

Calling tool calculator("expression": "123*456")...
56088
```

The LLM decides when to call which tool automatically — no manual orchestration needed.

### Running the App

The project includes `main.py` for convenience:

```bash
# Interactive chat
python main.py

# Single query
python main.py "What is 1+1?"

# Help
python main.py --help
```

`main.py` automatically imports tools from `tools/tools.py` (calculator, now, echo) and registers them.

---

## Development Guide

### Defining Tools — @tool {#defining-tool}

The `@tool` decorator turns any function into a callable tool. The function's parameter names and type annotations are automatically converted to a JSON Schema.

```python
from agentcore import AgentCore

app = AgentCore(api_key="sk-xxx")

@app.tool
def fetch_news(category: str, limit: int = 5) -> str:
    """Fetch top news headlines"""
    return f"Fetched {limit} {category} news"

@app.tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email"""
    return f"Email sent to {to}"
```

Tool functions should:
- Have descriptive names and docstrings (the LLM uses these to decide when to call)
- Use type annotations for parameters (auto-converts to JSON Schema)
- Execute quickly (the LLM is waiting)
- Be pure functions — **do not call `agent.chat()` inside a tool**

### Defining Skills — @skill {#defining-skill}

A **skill** is a multi-step workflow. Suitable for code reviews, report generation, multi-step data queries, etc. Skills can call `agent.chat()` multiple times internally.

```python
from agentcore.adapters.skill import SkillBase
from agentcore.adapters.decorators import skill

@skill
class ReportSkill(SkillBase):
    name = "report"
    description = "Generate a data analysis report"

    def run(self, agent, user_input: str) -> str:
        # Step 1: understand requirements
        requirements = agent.chat(f"Extract report requirements: {user_input}")

        # Step 2: query data (Agent may use registered tools)
        data = agent.chat(f"Query data based on: {requirements}")

        # Step 3: generate report
        return agent.chat(f"Generate a report from: {data}")
```

Trigger a skill by mentioning its name in conversation:

```
>>> report analyze last month's sales data
```

The distinction: **tools are atomic** (input→output, no `agent.chat()` inside); **skills orchestrate** (can call `agent.chat()` multiple times).

### Auto Registration — auto_register

Write tools and skills in modules, then register them in batch:

```python
import tools      # tools.py with @tool functions
import skills     # skills.py with @skill classes

app = AgentCore(api_key="sk-xxx")
app.auto_register(tools, skills)
```

`auto_register` scans modules and discovers:

| Writing | Becomes |
|---|---|
| `@tool def f():` | Tool |
| `class X(SkillBase):` | Skill |
| `class X(MemoryInterface):` | Replaces default memory |
| `class X(LLMClient):` | Replaces default LLM |

You can pass multiple modules:

```python
app.auto_register(tools, my_custom_skills)
```

### Using the Agent API Directly

Skip `AgentCore` and work with the Agent directly:

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

result = agent.chat("Hello")
print(result)
```

Use different `session_id` values to isolate conversations. Same `session_id` preserves context.

### Event Listeners

Each reasoning step produces a `StepRecord` containing the full chain (thought, action, action_input, observation). Register listeners for custom handling:

```python
def log_to_db(record):
    print(f"[{record.step}] {record.action} -> {record.observation[:50]}...")

agent.add_listener("db_logger", log_to_db)
```

The built-in JSONL file logger is implemented through the same mechanism.

### Timeout & Cancellation

Set timeouts for long-running conversations, or cancel from another thread:

```python
from threading import Event

cancel = Event()

# Call cancel.set() from another thread to interrupt
result = app.chat(
    "A time-consuming task",
    llm_timeout=30.0,    # LLM call timeout (seconds)
    tool_timeout=15.0,   # Tool execution timeout (seconds)
    max_steps=10,         # Max reasoning steps
    cancel_event=cancel,
)
```

In interactive mode, pressing Ctrl+C sends a cancel signal automatically.

---

## Memory

Default is sliding window memory (in-memory). It keeps the most recent N conversation turns per `session_id`. Older messages are discarded.

```python
# Adjust window size
app = AgentCore(window_size=20)

# Use Redis for persistence
from agentcore.services.memory.redis_memory import RedisMemory
app = AgentCore(memory=RedisMemory(host="localhost", port=6379))
```

**Memory** (conversation history) differs from **Checkpoints** (execution state) — see below.

---

## Checkpoints

When an Agent runs multi-step tasks (multiple tool calls), the process may crash. Checkpoints save execution state to a file after each step, allowing recovery from the point of failure.

```python
# Enabled by default, stored in .checkpoints/
app = AgentCore(checkpoint_dir=".checkpoints")

# List existing checkpoints
app.list_checkpoints()
# Output: [{"session_id": "default", "status": "in_progress", "step": 3, "max_steps": 10}]

# Resume after a crash
result = app.agent.resume(session_id="default")

# Clear a checkpoint
app.clear_checkpoint(session_id="default")
```

---

## Configuration

Three methods (priority descending):

1. **Code params** — `AgentCore(api_key="sk-xxx", model="gpt-4o")`
2. **Environment variable** — `set OPENAI_API_KEY=sk-xxx` (Windows) or `export OPENAI_API_KEY=sk-xxx` (Linux/Mac)
3. **Config file** — edit `resources/config.yaml`

```yaml
# resources/config.yaml
llm:
  model: "gpt-4o"
  api_key: "sk-xxx"
  base_url: ""           # Compatible OpenAI-format proxy URL
  temperature: 0.7
  max_tokens: 4096

memory:
  window_size: 10

runtime:
  pool_size: 4

log_path: logs/agentcore.jsonl
```

If multiple methods are used, explicit parameters override environment variables, which override the config file.

---

## Project Structure

```
├── main.py                     # Entry point
├── tools/tools.py              # Built-in tools (calculator, now, echo)
├── resources/config.yaml       # Configuration file
├── Dockerfile                  # Container deployment
├── pyproject.toml              # Project metadata
├── requirements.txt            # Python dependencies
│
└── agentcore/                  # Core library
    ├── __init__.py             # Exports AgentCore
    ├── app.py                  # AgentCore launcher
    │
    ├── core/                   # Core engine
    │   ├── interfaces.py       # Abstract interfaces
    │   ├── orchestrator.py     # ReAct reasoning loop
    │   ├── parser.py           # Fault-tolerant JSON parser
    │   └── tool_manager.py     # Tool registry & execution
    │
    ├── runtime/                # Runtime components
    │   ├── runner.py           # Sync runner
    │   ├── waiter.py           # Thread pool with timeout guard
    │   ├── broadcaster.py      # Event dispatch
    │   └── checkpointer.py     # Checkpoint persistence
    │
    ├── adapters/               # Adapter layer
    │   ├── agent.py            # Agent wrapper
    │   ├── builder.py          # Build Agent from YAML
    │   ├── cli.py              # CLI entry point
    │   ├── decorators.py       # @tool / @skill decorators
    │   └── skill.py            # SkillBase
    │
    ├── services/               # Service implementations
    │   ├── llm/
    │   │   ├── openai_sdk.py   # OpenAI SDK client
    │   │   └── http_client.py  # HTTP client
    │   ├── memory/
    │   │   ├── sliding_window.py  # Sliding window memory
    │   │   └── redis_memory.py    # Redis persistence
    │   ├── tools/
    │   │   ├── calculator_tool.py # Calculator
    │   │   └── datetime_tool.py   # Date & time
    │   └── logger/
    │       └── file_logger.py     # JSONL file logger
    │
    ├── tests/                  # Tests
    │   ├── unit/               # Unit tests
    │   ├── integration/        # Integration tests
    │   └── chaos/              # Chaos tests (timeout/cancel)
    │
    └── examples/               # Examples
        ├── quick_start.py
        └── code_review_skill.py
```

### Execution Flow

```
User Input
    │
    ▼
AgentCore → Agent.chat()
              │
              ├─ Skill triggered? → Execute skill (may call chat() again)
              │
              └─ SyncRunner → Orchestrator (ReAct loop)
                                │
                                ├─ ① LLM inference
                                ├─ ② JSON parsing
                                ├─ ③ Tool execution
                                ├─ ④ Save checkpoint
                                └─ ⑤ Broadcast event
                                      │
                                      ▼
                                FileLogger writes JSONL
```

---

## Deployment

### Docker

```bash
docker build -t agentcore .
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=sk-xxx \
  -v ./logs:/app/logs \
  agentcore
```

Health check: `GET /health`

### Horizontal Scaling

Agent instances are stateless (state is stored in Redis or checkpoint files). Multi-instance deployment:

```
        Load Balancer
         /    \
    Agent1   Agent2
         \    /
         Redis (session state)
```
