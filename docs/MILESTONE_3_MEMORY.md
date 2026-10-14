# Milestone 3: Simple Long-Term Memory

ATHENA now has a small local memory file:

```text
memory/profile.md
```

This file is loaded into the chat at startup so ATHENA can remember stable facts.

## Commands

Show memory:

```text
/memory
```

Save a new memory:

```text
/remember My main project is ATHENA.
```

Quit:

```text
/exit
```

If a memory looks like a password, API key, or SSH key, ATHENA warns you. `memory/profile.md` can be committed. `memory/private.md` is gitignored and is not loaded into the chat.

## What To Store

Good memories:

- Your machine has 8 GB memory
- You prefer lightweight local tools first
- ATHENA should avoid claiming internet access
- Your main technology interests are Python, Docker, Kubernetes, OpenStack, and Jenkins

Avoid storing secrets:

- Passwords
- API keys
- Private tokens
- SSH keys

Put very sensitive notes in `memory/private.md` if needed. That file is ignored by Git.

## Why This Comes Before RAG

RAG and vector databases are useful, but they add moving parts. This memory file gives ATHENA useful continuity with almost no overhead.
