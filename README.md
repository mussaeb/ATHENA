# Project ATHENA

ATHENA is a local-first personal AI assistant for an 8 GB machine.

It talks to a small model through Ollama, keeps notes and documents on disk, and can use the web, voice, project files, and infrastructure tools when you ask. Every script uses the Python standard library.

## Current State

The lightweight roadmap is in place:

- Local chat through Ollama
- Saved chats, session names, and search over past chats
- Long-term memory in `memory/profile.md`
- Keyword document search
- Web search with source URLs
- Operating-system speech
- Read-only project inspection, tests, and reviewed file edits
- Read-only Docker, Kubernetes, Jenkins, and OpenStack checks
- Approved multi-step plans
- Optional image description when you choose a vision model

Normal chat does not search the web or your documents until you turn those modes on. ATHENA is told to say when it does not have a live source.

## Quick Start

1. Check the machine:

```bash
python3 scripts/athena_check.py
```

2. Install Ollama from [https://ollama.com/download](https://ollama.com/download).

3. Pull a small model:

```bash
ollama pull qwen2.5:1.5b
```

4. Start ATHENA:

```bash
python3 scripts/athena_chat.py
```

Or open the local page, which adds a microphone button and a code view:

```bash
python3 scripts/athena_ui.py
```

That opens http://127.0.0.1:8765. Leave that window open while you use the page. **Code** starts in this folder. **Open project** switches it to another folder on this computer. Open a file to edit it, then **Save**. Keep several files in tabs. **New file** creates one in the folder you are browsing. Ctrl+P opens a file by name, Ctrl+F finds in the file, and Ctrl+G jumps to a line. Ask ATHENA from the box above the editor. The question moves into **Replies**, and a follow-up can refer to the recent ones; **Clear** starts over. **Apply** writes a reviewed draft. Drag the dividers to resize the file list and the bottom panel, or hide either one.

On Windows, use `python` instead of `python3`.

If the 1.5B model feels comfortable:

```bash
ollama pull qwen2.5:3b
ATHENA_MODEL=qwen2.5:3b python3 scripts/athena_chat.py
```

If responses feel slow, use a smaller context:

```bash
ATHENA_NUM_CTX=1024 python3 scripts/athena_chat.py
```

Copy `config/athena.example.env` to `.env` when you want those settings loaded automatically.

## Useful Commands

Type `/help` inside the chat for the full list.

```text
/remember My Mac has 8 GB memory.
/name project-review
/history ATHENA memory
/recall what did we decide about documents?
/search ATHENA memory
/askdocs what can ATHENA do now?
/web Python release
/askweb what is the current stable Python version?
/speak on
/git
/read README.md
/plan summarize the README and the git status
/approve
/exit
```

`/propose README.md Mention the test command` drafts a diff. `/apply yes` writes it after you review that diff.

## Tests

The tests do not need Ollama:

```bash
python3 -m unittest discover -s tests -v
```

## 8 GB Rule

For now, do not run all of these at the same time:

- Docker Desktop
- An editor with many extensions
- A browser with many tabs
- An Ollama model
- Open WebUI

The local page stays on this computer and does not add a second model. A hosted interface such as Open WebUI, vector databases, and a Docker-based stack wait until the machine has more memory.

## Project Map

- `docs/` - setup, roadmap, architecture, and milestone notes
- `scripts/` - local commands
- `config/` - example settings
- `memory/` - long-term memory
- `rag/` - document sources and the local keyword index
- `voice/` - speech notes; the command is `scripts/athena_voice.py`
- `vision/` - image notes; vision stays off until `ATHENA_VISION_MODEL` is set
- `infrastructure/` - read-only infrastructure notes; the command is `scripts/athena_infra.py`
- `tests/` - unit tests for the standard-library tools
- `logs/` - chats, proposals, plans, and the safety log

## GitHub

See [docs/GITHUB_SETUP.md](docs/GITHUB_SETUP.md).
