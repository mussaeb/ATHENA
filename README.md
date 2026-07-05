# Project ATHENA

ATHENA is your local-first personal AI assistant project.

The first version is intentionally small because this Mac has 8 GB of memory. We will start with a lightweight local model through Ollama, a simple terminal chat client, and clear documentation. Later phases add memory, document search, voice, vision, Docker, Kubernetes, Jenkins, and OpenStack.

## Current Milestone

Milestone 1: foundation for an 8 GB Mac.

Included now:

- Project structure for the full ATHENA roadmap
- Mac setup guide tuned for low memory
- Dependency-free Python health check
- Dependency-free Python Ollama chat client
- Example configuration file

## Quick Start

1. Check your machine:

```bash
python3 scripts/athena_check.py
```

2. Install Ollama from:

[https://ollama.com/download](https://ollama.com/download)

3. Start with a small model:

```bash
ollama pull qwen2.5:1.5b
```

4. Chat with ATHENA:

```bash
python3 scripts/athena_chat.py
```

If the 1.5B model feels comfortable, try:

```bash
ollama pull qwen2.5:3b
ATHENA_MODEL=qwen2.5:3b python3 scripts/athena_chat.py
```

## 8 GB Rule

For now, do not run all of these at the same time:

- Docker Desktop
- VS Code with many extensions
- Browser with many tabs
- Ollama model
- Open WebUI

On this Mac, ATHENA should begin as a terminal assistant. Once the core works, we can add a web UI carefully.

## Project Map

- `docs/` - setup, roadmap, architecture, decisions
- `scripts/` - local commands and helper tools
- `config/` - example settings
- `memory/` - later long-term memory store
- `rag/` - later document search system
- `voice/` - later speech-to-text and text-to-speech
- `vision/` - later image and screenshot understanding
- `infrastructure/` - later Docker, Kubernetes, OpenStack, Jenkins integrations
- `tests/` - tests for ATHENA code

## Next Milestones

1. Local chat through Ollama
2. Save conversation history
3. Add simple memory notes
4. Add document search
5. Add internet search
6. Add voice input and output
7. Add infrastructure tools
