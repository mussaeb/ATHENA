# Push ATHENA to GitHub

You have two good options.

## Option 1: GitHub CLI

Check if GitHub CLI is installed:

```bash
gh --version
```

If it is missing:

```bash
brew install gh
```

Log in:

```bash
gh auth login
```

From the ATHENA folder:

```bash
cd /Users/home/ATHENA
gh repo create ATHENA --private --source=. --remote=origin --push
```

Use `--public` instead of `--private` if you want the project visible to everyone.

## Option 2: GitHub Website

1. Open GitHub.
2. Create a new repository named `ATHENA`.
3. Do not add a README, license, or `.gitignore` on GitHub because this project already has local files.
4. Copy the repository URL.

Then run:

```bash
cd /Users/home/ATHENA
git remote add origin git@github.com:YOUR_USERNAME/ATHENA.git
git push -u origin main
```

If you prefer HTTPS:

```bash
cd /Users/home/ATHENA
git remote add origin https://github.com/YOUR_USERNAME/ATHENA.git
git push -u origin main
```

## Current Local Commit Commands

Run these after reviewing the files:

```bash
cd /Users/home/ATHENA
git add .gitignore README.md docs/SETUP_MAC_8GB.md docs/MILESTONE_2_HISTORY.md docs/MILESTONE_3_MEMORY.md docs/GITHUB_SETUP.md docs/ROADMAP.md scripts/athena_chat.py memory/profile.md
git commit -m "Add local-mode guardrails, chat history, and memory"
```

For document search:

```bash
cd /Users/home/ATHENA
git add .gitignore README.md config/document_sources.example.json docs/GITHUB_SETUP.md docs/ROADMAP.md docs/MILESTONE_4_DOCUMENT_SEARCH.md scripts/athena_chat.py scripts/athena_docs.py rag/sources/.gitkeep rag/sources/athena-overview.md
git commit -m "Add lightweight local document search"
```

Then push:

```bash
git push -u origin main
```
