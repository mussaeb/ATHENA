# ATHENA Architecture

ATHENA starts small and grows in layers. The current layers are all local Python scripts.

```text
User
  |
  v
ATHENA chat (scripts/athena_chat.py)
  |
  v
Local model through Ollama
  |
  +--> memory/profile.md
  +--> document keyword index
  +--> web search with saved URLs
  +--> operating-system speech
  +--> optional vision model
  +--> project files, git, and tests
  +--> read-only infrastructure checks
  +--> approved allowlisted plan steps
```

## Layer 1: Client

The client is `scripts/athena_chat.py`.

It is dependency-free and talks to the local Ollama API at:

```text
http://127.0.0.1:11434/api/chat
```

On Windows or Mac it uses the same Python interpreter that launched the chat when it calls the other scripts.

## Layer 2: Model

For 8 GB memory, start with:

```text
qwen2.5:1.5b
```

Good next step:

```text
qwen2.5:3b
```

Larger models should wait until the machine has more memory or ATHENA is moved to a dedicated AI workstation. The chat sends only the system prompt, memory, and a short recent window to the model.

## Layer 3: Memory

Memory is a human-readable Markdown file:

- `memory/profile.md` is loaded into the chat
- `memory/private.md` is gitignored and is not loaded

## Layer 4: Retrieval

Document search extracts text and ranks chunks by keyword overlap. Web search asks DuckDuckGo lite, then Wikipedia, and keeps the result URL with each hit. Vector search can come later.

The model may cite a document, a past chat, or a URL only when that tool result was attached to the current question.

## Layer 5: Tools

Project inspection and infrastructure checks are read-only:

- Git status, diff, and log
- Project file reads inside the repository
- Unit tests
- Docker status
- Kubernetes pods
- Jenkins job colors
- OpenStack server list

File edits go through a reviewed diff and `/apply yes`. Plans can run only the verbs in `scripts/athena_agent.py`. Shell commands are rejected. Writes and approvals are appended to `logs/safety/safety.jsonl`.

## Layer 6: Voice And Vision

Speech uses the operating system: `say` on macOS, Windows Speech on Windows, and `espeak` when that command exists. Push-to-talk currently uses the Windows speech recognizer.

Vision sends one image to Ollama only when `ATHENA_VISION_MODEL` is set. The default chat model stays text-only.
