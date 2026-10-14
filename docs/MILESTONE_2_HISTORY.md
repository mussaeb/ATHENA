# Milestone 2: Conversation History

ATHENA now saves each terminal chat as a local JSONL file.

## Where Chats Are Stored

```text
logs/chats/
```

Each line is one message with:

- timestamp
- model
- role
- content

## Why This Matters

This is the first step toward memory. Before ATHENA can remember useful things, it needs a reliable local record of conversations.

## Session Names

Name the open chat:

```text
/name project-review
```

The transcript file is renamed, and later lines include the session name.

## Search Past Chats

List recent transcripts:

```text
/sessions
```

Search them:

```text
/history Kubernetes
```

Ask ATHENA to answer from the matches:

```text
/recall what did we decide about memory?
```

From the terminal:

```bash
python3 scripts/athena_history.py list
python3 scripts/athena_history.py search Kubernetes
```

Ordinary questions still use the current conversation and `memory/profile.md`. Past chats are included when you use `/history` or `/recall`.

Milestone 3 keeps durable facts in `memory/profile.md`, which is loaded at startup. Chat search stays a separate command so a long history does not fill the small context window.
