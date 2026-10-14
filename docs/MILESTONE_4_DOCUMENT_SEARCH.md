# Milestone 4: Local Document Search

ATHENA can now index and search local documents without a vector database.

## Option 1: Put Documents Inside ATHENA

Put files here:

```text
rag/sources/
```

Supported file types:

- `.md`
- `.txt`
- `.log`
- `.csv`
- `.json`
- `.yaml`
- `.yml`
- `.py`
- `.docx`
- `.xlsx`
- `.pdf` if `pdftotext` is installed

Personal documents in `rag/sources/` are ignored by Git by default.

## Option 2: Index Chosen Folders On Your Mac

You do not have to copy everything into `rag/sources/`.

From ATHENA chat, run:

```text
/initdocs
```

This creates:

```text
config/document_sources.json
```

Use this shape:

```json
{
  "sources": [
    "~/Documents",
    "~/Desktop",
    "/Users/home/ATHENA/rag/sources"
  ]
}
```

Then run:

```text
/index
```

The config file is ignored by Git so your personal folder list is not pushed to GitHub.

To check what ATHENA can currently see:

```text
/sources
```

If `/sources` only shows `rag/sources`, ATHENA cannot search your Desktop or Documents yet.

## Why Not Index The Whole Computer?

Indexing the whole computer is risky and noisy.

It can accidentally read:

- passwords or tokens
- SSH keys
- browser data
- caches
- application support files
- private photos or messages
- huge folders that make indexing slow

ATHENA is safer when it uses an allowlist of folders you choose.

The indexer skips common noisy folders such as `.git`, `.ssh`, `Library`, `.cache`, `node_modules`, and virtual environments.

For broad folders like `~/Documents` or `~/Downloads`, ATHENA also uses safety limits:

```text
ATHENA_DOCS_MAX_FILES=250
ATHENA_DOCS_MAX_DEPTH=5
```

You can raise them when needed:

```bash
ATHENA_DOCS_MAX_FILES=500 ATHENA_DOCS_MAX_DEPTH=7 python3 scripts/athena_chat.py
```

For best results, point ATHENA at focused folders such as `~/Documents/Resumes` or `~/Downloads/ATHENA`, not your entire home directory.

## Index Documents

From ATHENA chat:

```text
/index
```

From the terminal:

```bash
python3 scripts/athena_docs.py index
```

## Search Documents

`/search` looks through local documents. `/web` is the internet command.

From ATHENA chat:

```text
/search ATHENA memory
```

Use your real topic in place of `ATHENA memory`. For example:

```text
/search resume python
```

Find files by name:

```text
/findfile resume
```

From the terminal:

```bash
python3 scripts/athena_docs.py search ATHENA memory
```

## Ask ATHENA Using Documents

From ATHENA chat:

```text
/askdocs what can ATHENA do now?
```

ATHENA will search local documents, pass the matching chunks to the model, and answer from those results.

Normal chat questions do not use documents unless document mode is on.

Turn document mode on:

```text
/docmode on
```

Then normal questions will use local document search:

```text
what experience do I have with Kubernetes?
```

Turn it off:

```text
/docmode off
```

If you type an unknown slash command like `/indexes`, ATHENA will show a command help hint instead of sending it to the model.

## PDF Support

PDF support uses `pdftotext`.

Install it with:

```bash
brew install poppler
```

Then put PDFs into:

```text
rag/sources/
```

Run:

```text
/index
```

## Why This Is Lightweight

This milestone uses simple keyword search instead of embeddings and a vector database.

That is intentional for an 8 GB Mac. It keeps ATHENA useful, understandable, and easy to fix. Later we can add embeddings when the local foundation is stable.
