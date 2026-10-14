# ATHENA Overview

ATHENA is a local-first personal AI assistant for engineering, learning, and personal productivity.

The original target machine is an Apple Silicon Mac with 8 GB of memory, so ATHENA prefers lightweight tools before Docker-heavy services. The same scripts run on Windows with Python 3.9 or newer.

Current capabilities:

- Local chat through Ollama
- Chat history, session names, and search over saved chats
- Long-term memory from memory/profile.md
- Keyword document search from rag/sources and optional folders listed in config/document_sources.json
- Web search with source URLs through /web, /askweb, and /webmode
- Speech through the operating system, with push-to-talk on Windows and Mac
- A local page at scripts/athena_ui.py for chat, microphone input, and reviewed edits
- Project inspection, unit tests, and reviewed file edits
- Read-only Docker, Kubernetes, Jenkins, and OpenStack status
- Approved plans that can run only an allowlist of tools
- Optional image description when ATHENA_VISION_MODEL is set

Ordinary questions use the model and memory only. Documents, the web, and past chats are attached when you use the matching command or mode.

Still waiting for a larger machine:

- A hosted interface such as Open WebUI
- Vector search
- A wake word
- Scheduled checks
- Infrastructure changes
