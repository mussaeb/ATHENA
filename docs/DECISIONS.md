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

The first scripts use only the Python standard library.

Reason:

- No virtual environment required for milestone 1
- Fewer installation problems
- Easier to run on a fresh Mac
