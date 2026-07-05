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

## What This Is Not Yet

Saved logs are not the same as active memory. At this stage, ATHENA writes chats to disk, but it does not automatically read old chats before answering.

That comes next.

## Next Step

Milestone 3 will add a small human-readable memory file, so you can teach ATHENA durable facts like:

```text
My main project is ATHENA.
My Mac has 8 GB of memory.
Prefer lightweight local tools first.
```
