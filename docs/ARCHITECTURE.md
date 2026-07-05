# ATHENA Architecture

ATHENA starts small and grows in layers.

```text
User
  |
  v
ATHENA client
  |
  v
Local model through Ollama
  |
  +--> memory
  +--> documents
  +--> internet search
  +--> voice
  +--> infrastructure tools
```

## Layer 1: Client

The first client is `scripts/athena_chat.py`.

It is dependency-free and talks to the local Ollama API at:

```text
http://127.0.0.1:11434/api/chat
```

## Layer 2: Model

For 8 GB memory, start with:

```text
qwen2.5:1.5b
```

Good next step:

```text
qwen2.5:3b
```

Larger models should wait until the machine has more memory or ATHENA is moved to a dedicated AI workstation.

## Layer 3: Memory

The first memory version should be simple:

- Local Markdown or JSON files
- Human-readable facts
- No database at first

This keeps the system understandable and easy to repair.

## Layer 4: Retrieval

Document search can begin with local text extraction and simple keyword search. Vector search can come later when the project needs it.

## Layer 5: Tools

Infrastructure integrations should be read-only first:

- Docker status
- Kubernetes pods and events
- Jenkins build logs
- OpenStack server status

Write actions should require explicit approval.
