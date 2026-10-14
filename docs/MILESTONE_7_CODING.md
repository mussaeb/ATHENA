# Milestone 7: Coding Assistant

ATHENA can inspect this repository, run its tests, and draft a reviewed edit.

## Read

```text
/git
/git diff
/log
/read README.md
/files athena
/test
```

`/read` stays inside the project and refuses `.env`, private keys, and `memory/private.md`.

From the terminal:

```bash
python3 scripts/athena_code.py git-status
python3 scripts/athena_code.py test
```

## Draft An Edit

```text
/propose vision/README.md Mention that /listen is push-to-talk.
```

ATHENA returns a diff and writes nothing. Read it, then:

```text
/apply yes
```

`/apply` without `yes` shows the latest diff again.

The draft replaces one exact snippet. The snippet must appear once. If the file changed after the draft, apply stops and you create a new proposal. New files are allowed only under the project directories ATHENA already uses for source, docs, tests, config, and memory.

Large files are refused while `ATHENA_NUM_CTX` is small. Raise it when the machine can afford the extra context:

```bash
ATHENA_NUM_CTX=4096 python3 scripts/athena_chat.py
```

The default 1536 context is there to protect an 8 GB machine. A full-file rewrite does not fit in that window, so the editor asks for the smallest unique snippet instead.
