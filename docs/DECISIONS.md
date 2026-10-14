# ATHENA Decisions

## 001: Start lightweight on 8 GB

ATHENA starts as a terminal-first project rather than a Docker-heavy stack.

Reason:

- 8 GB memory is enough for small local models
- Docker plus a browser UI can consume too much memory
- A small foundation is easier to understand and debug

## 002: Use Ollama first

Ollama provides a simple local model server with a stable local API.

Reason:

- Easy install on macOS
- Good Apple Silicon support
- Works without writing model-loading code

## 003: Use dependency-free scripts first

The scripts use only the Python standard library.

Reason:

- No virtual environment required
- Fewer installation problems
- Easier to run on a fresh machine

## 004: Search only when asked

Normal chat does not call the web or document index. `/web`, `/askweb`, `/webmode`, `/search`, `/askdocs`, and `/docmode` attach real results, including URLs or file paths.

Reason:

- Small models sometimes claim they searched when they did not
- The user can see which source was actually used

## 005: Reviewed edits

`/propose` drafts a snippet replacement and shows a diff. `/apply yes` writes the file after checking that it has not changed since the draft. Secrets, `.env`, and paths outside the project are refused.

Reason:

- A 1.5B model with a small context window should not rewrite a large file blindly
- The user gets a chance to read the change

## 006: Allowlisted plans

`/plan` may use only the verbs in `scripts/athena_agent.py`. `/approve` runs one pending step. Shell commands, file writes, and unknown verbs are rejected.

Reason:

- The plan should stay understandable on a small model
- Approval is meaningful when the step cannot escape the list

## 007: Infrastructure is read-only

Docker, Kubernetes, Jenkins, and OpenStack helpers report status. They do not create, delete, or change resources.

Reason:

- A wrong write against a cluster is expensive to undo
- Status is enough to explain an incident

## 008: Use the operating system for speech

Text-to-speech and push-to-talk call the speech tools already installed with the operating system.

Reason:

- Whisper, Piper, and extra Python packages can be added later on a larger machine
- The 8 GB machine does not need another model loaded for a first voice loop

## 009: A local page, with the browser only for the microphone

`scripts/athena_ui.py` serves one page on 127.0.0.1. Spoken replies still use the operating system voice. The Listen button uses the browser speech recognizer because macOS has no dependency-free dictation command. `/listen` on a Mac uses on-device recognition when the Swift tools are installed.

Reason:

- Open WebUI and another model do not fit the 8 GB budget
- Chat, document search, web search, and reviewed edits can share one page without a frontend toolchain
- Chrome's recognizer is not fully local, so the page says that plainly
- The page terminal runs only commands the user types, and file writes still wait for Apply
