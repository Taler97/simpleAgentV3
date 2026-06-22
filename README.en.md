# AgentCore V3 — Synchronous · Pluggable · ReAct Agent Framework

A **synchronous** AI Agent runtime framework built around a **ReAct (Reasoning-Action-Observation) loop**. It enables an LLM to iteratively reason, invoke tools, observe results, and produce a final answer.

---

## Design Philosophy

### Synchronous by Default, Complexity by Exception

No asyncio. No event loops. No coroutines. Concurrency is handled by a thread pool, and every execution path is linear — meaning you can trace the full call chain with a single `print` statement. Debugging feels like writing plain Python scripts.

### Pluggable Architecture

LLM, memory, logger — every component follows a Protocol interface. The framework is not coupled to any specific implementation, and swapping implementations does not require changing framework code.

```
AgentCore → Agent → Orchestrator (ReAct loop)
                      ├─ LLM (OpenAI / DeepSeek / custom)
                      ├─ Memory (sliding window / Redis / custom)
                      ├─ Tools (@tool decorator / MCP protocol)
                      └─ Logger (JSONL file / custom listener)
```

### Security by Default

- The calculator uses AST whitelist evaluation, not `eval()`
- Every LLM call and tool execution has an independent timeout guard
- Supports graceful `Ctrl+C` cancellation
- Loop detection prevents infinite Agent loops

### Principle of Least Surprise

A single `@tool` decorator turns a function into a callable Agent tool. No magic, no modified signatures, no mandatory base classes. The framework is infrastructure — your business logic stays clean.

---

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Configuration

Edit [resources/config.yaml](file:///resources/config.yaml) and fill in your LLM API Key:

```yaml
llm:
  model: "gpt-4o"
  api_key: "sk-xxx"              # Replace with your key
  base_url: ""                   # Optional proxy URL (OpenAI-compatible)
```

Supports OpenAI, DeepSeek, and any provider with an OpenAI-compatible API.

### Launch

```bash
# Interactive chat
python -m agentcore.adapters.cli

# Single query
python -m agentcore.adapters.cli "What is 1+1?"

# Custom config file
python -m agentcore.adapters.cli -c resources/config.yaml
```

In interactive mode:

```
>>> What time is it?

>>> What is 123 * 456?
```

The LLM automatically calls registered tools to answer.

### Register as CLI Command

```bash
pip install -e .
agentcore                    # Interactive mode
agentcore "Hello"            # Single query
```

---

## Five-Minute Example

Create `run.py`:

```python
from agentcore import AgentCore

app = AgentCore(api_key="sk-xxx")

@app.tool
def get_weather(city: str) -> str:
    """Get weather for a city"""
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

```bash
python run.py
```

---

## Core Concepts

### Tool — `@tool`

A tool is an **atomic operation**: input → output. Do **not** call `agent.chat()` inside a tool.

```python
@app.tool
def fetch_news(category: str, limit: int = 5) -> str:
    """Fetch top news headlines"""
    return f"Fetched {limit} {category} news"
```

The function name, docstring, and type annotations are automatically converted to a JSON Schema that the LLM uses to decide when to call this tool.

### Skill — `@skill`

A skill is a **multi-step workflow** that can call `agent.chat()` multiple times internally.

```python
from agentcore.adapters.skill import SkillBase
from agentcore.adapters.decorators import skill

@skill
class ReportSkill(SkillBase):
    name = "report"
    description = "Generate a data analysis report"

    def run(self, agent, user_input: str) -> str:
        req = agent.chat(f"Extract requirements: {user_input}")
        data = agent.chat(f"Query data for: {req}")
        return agent.chat(f"Generate report from: {data}")
```

Mention the skill name in conversation to trigger it.

### Auto Registration

Write tools and skills in modules, then batch-register:

```python
app.auto_register(tools_module, skills_module)
```

`auto_register` discovers `@tool` functions, `SkillBase` subclasses, and custom `LLMClient`/`MemoryInterface` implementations.

---

## Architecture

### Project Structure

```
agentcore/
├── __init__.py           # Exports AgentCore
├── app.py                # Launcher (decorators, lifecycle)
├── mcp.py                # MCP client (STDIO transport)
│
├── core/                 # Core engine
│   ├── interfaces.py     # Abstract interfaces
│   ├── orchestrator.py   # ReAct reasoning loop
│   ├── parser.py         # Fault-tolerant JSON parser
│   └── tool_manager.py   # Tool registry & execution
│
├── runtime/              # Runtime components
│   ├── runner.py         # Generator driver
│   ├── waiter.py         # Thread-pool guard (timeout/cancel)
│   ├── checkpointer.py   # Checkpoints (crash recovery)
│   └── broadcaster.py    # Event dispatch
│
├── adapters/             # Adapter layer
│   ├── agent.py          # Agent wrapper (.chat() entry point)
│   ├── cli.py            # CLI entry point
│   ├── decorators.py     # @tool / @skill decorators
│   └── skill.py          # SkillBase
│
└── services/             # Service implementations
    ├── llm/openai_sdk.py       # OpenAI SDK client
    ├── memory/
    │   ├── sliding_window.py   # In-memory sliding window (default)
    │   └── redis_memory.py     # Redis persistence
    ├── tools/
    │   ├── calculator_tool.py  # Safe calculator (AST evaluation)
    │   └── datetime_tool.py    # Date & time
    └── logger/file_logger.py   # JSONL file logger
```

### Execution Flow

```
User Input
    │
    ▼
AgentCore.run()
    │
    ▼
Agent.chat()
    ├─ Skill matched? → Execute skill (may call chat() multiple times)
    │
    └─ SyncRunner → Orchestrator.run()  (ReAct loop)
                      │
                      ├─ ① LLM.generate(messages)
                      ├─ ② Parser.parse() fault-tolerant JSON
                      ├─ ③ action=""? → return final answer
                      ├─ ④ ToolManager.execute() run tool
                      ├─ ⑤ Append observation to messages, loop
                      ├─ ⑥ Loop detection (prevent infinite loops)
                      └─ ⑦ FileCheckpointer saves state
                            │
                            ▼
                      Broadcaster → FileLogger writes JSONL
```

---

## Features

### Fault-Tolerant JSON Parsing

The Parser automatically fixes common LLM JSON issues: single quotes instead of double quotes, trailing commas, markdown code blocks, line comments, etc.

### Timeout & Cancellation

Every LLM call and tool execution has an independent timeout. Supports `Ctrl+C` cancellation:

```python
from threading import Event

cancel = Event()
result = app.agent.chat(
    "Long task",
    llm_timeout=30.0,
    tool_timeout=15.0,
    max_steps=10,
    cancel_event=cancel,
)
```

### Checkpoint Recovery

If the process crashes mid-execution, resume from the last checkpoint:

```python
# List checkpoints
app.list_checkpoints()

# Resume
result = app.agent.resume(session_id="default")

# Clear
app.clear_checkpoint(session_id="default")
```

### Event Listeners

Each reasoning step produces a `StepRecord` with the full chain (thought, action, action_input, observation):

```python
def my_listener(record):
    print(f"[{record.step}] {record.action} -> {record.observation[:50]}")

agent.add_listener("my_logger", my_listener)
```

The built-in JSONL file logger is implemented through the same mechanism.

### MCP Protocol Support

Start an MCP Server subprocess via STDIO and auto-register its tools. Configure in [resources/config.yaml](file:///resources/config.yaml):

```yaml
mcp_servers:
  - name: filesystem
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "."]
```

### Memory

| Implementation | Description |
|---------------|-------------|
| `SlidingWindowMemory` | In-memory sliding window, keeps N recent turns per session_id |
| `RedisMemory` | Redis-backed persistence with TTL |

### Health Check

```bash
python -m agentcore.adapters.cli --host 0.0.0.0 --port 8080
# Visit http://localhost:8080/health
```

---

## Configuration

Three methods (priority descending):

1. **Code params** — `AgentCore(api_key="sk-xxx", model="gpt-4o")`
2. **Environment variable** — `OPENAI_API_KEY=sk-xxx`
3. **Config file** — `resources/config.yaml`

---

## Deployment

```bash
docker build -t agentcore .
docker run -p 8080:8080 -e OPENAI_API_KEY=sk-xxx agentcore
```
