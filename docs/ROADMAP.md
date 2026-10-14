# ATHENA Roadmap

Each milestone should leave the project in a working state. These milestones are implemented in the lightweight, standard-library form that fits an 8 GB machine.

## Phase 1: Foundation

- Create the project structure
- Add setup documentation
- Add health checks
- Add basic local chat

Done when ATHENA can talk to a local Ollama model from the terminal.

Status: implemented in `scripts/athena_check.py` and `scripts/athena_chat.py`.

## Phase 2: Conversation History

- Save chats to local files
- Add simple session names
- Add basic search over past chats

Done when ATHENA can recall earlier conversation files.

Status: implemented with `logs/chats`, `/name`, `/sessions`, `/history`, and `/recall`.

## Phase 3: Personal Memory

- Add a small local memory file
- Let the user add facts manually
- Let ATHENA read those facts before answering

Done when ATHENA can remember stable facts like project names, people, and preferences.

Status: implemented with `memory/profile.md` and `/remember`.

## Phase 4: Document Search

- Add a documents folder
- Extract text from PDFs, Word files, and text files
- Add lightweight retrieval

Done when ATHENA can answer questions from your own documents.

Status: implemented with `rag/sources`, `scripts/athena_docs.py`, `/search`, and `/askdocs`.

## Phase 5: Internet Search

- Add search tool integration
- Add source tracking
- Summarize current information safely

Done when ATHENA can answer questions that need fresh information.

Status: implemented with `scripts/athena_web.py`, `/web`, `/askweb`, and `/webmode`. Results keep their URLs.

## Phase 6: Voice

- Add speech-to-text
- Add text-to-speech
- Add push-to-talk first, wake word later

Done when you can speak to ATHENA and hear the response.

Status: text-to-speech and one-shot push-to-talk are implemented in `scripts/athena_voice.py`. Mac terminal listening uses on-device recognition when Swift is installed. The local page listens through the browser. A wake word is still later.

## Phase 7: Coding Assistant

- Add Git helpers
- Add project file reading
- Add patch generation
- Add test execution

Done when ATHENA can help edit and verify local code.

Status: implemented with `/git`, `/read`, `/files`, `/test`, `/propose`, and `/apply yes`.

## Phase 8: Infrastructure Assistant

- Add Docker helpers
- Add Kubernetes helpers
- Add Jenkins helpers
- Add OpenStack helpers

Done when ATHENA can inspect infrastructure safely and explain issues.

Status: implemented as read-only checks in `scripts/athena_infra.py`.

## Phase 9: Agents and Automation

- Add planned tool use
- Add approval gates
- Add scheduled checks
- Add safety logs

Done when ATHENA can perform multi-step tasks with user approval.

Status: `/plan`, `/approve`, and `/reject` run an allowlist one step at a time. Each approval or file write is appended to `logs/safety/safety.jsonl`. Scheduled checks are still later.

## Later, On A Larger Machine

- A hosted interface such as Open WebUI
- Vector search
- Wake word
- Scheduled checks
- Infrastructure changes, still behind an approval gate
