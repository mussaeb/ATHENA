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

## Review Before You Commit

The early milestone commits are already in the local history. Later work adds web search, voice, project tools, infrastructure checks, and approved plans.

Before committing new work:

```bash
git status
git diff
```

Leave out `.env`, `config/document_sources.json`, `memory/private.md`, and `logs/`. Those can contain personal notes, folder lists, or tokens.

Then push:

```bash
git push -u origin main
```
