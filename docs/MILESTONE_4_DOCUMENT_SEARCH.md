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

Create this file:

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

From ATHENA chat:

```text
/search ATHENA memory
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
