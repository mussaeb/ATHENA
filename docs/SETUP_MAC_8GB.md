# ATHENA Setup for an 8 GB Apple Silicon Mac

This setup is designed for a MacBook M1 Pro with limited memory. The goal is to get a useful assistant running without overloading the machine.

## Recommended Starting Stack

- macOS on Apple Silicon
- Python 3
- Ollama
- One small local model
- Terminal-based ATHENA client

Avoid starting with Docker, Open WebUI, vector databases, or Kubernetes. They are useful later, but they add memory pressure too early.

## Step 1: Check the Mac

From the ATHENA folder:

```bash
python3 scripts/athena_check.py
```

You want to see:

- Apple Silicon detected
- Python detected
- Ollama detected after installation
- Docker optional

## Step 2: Install Ollama

Download Ollama:

[https://ollama.com/download](https://ollama.com/download)

After installation, check:

```bash
ollama --version
```

## Step 3: Pull a Small Model

Start here:

```bash
ollama pull qwen2.5:1.5b
```

This is the best first model for an 8 GB machine because it leaves enough memory for macOS and your editor.

If performance is good, try:

```bash
ollama pull qwen2.5:3b
```

Avoid larger models at this stage. A 7B model may run, but on 8 GB it can feel slow and can cause memory pressure.

## Step 4: Run ATHENA Chat

```bash
python3 scripts/athena_chat.py
```

Ollama does not search the internet by itself. A normal question has no web results attached.

If you ask:

```text
did you check the internet?
```

the correct behavior is to say no, unless you used `/web`, `/askweb`, or `/webmode on` for that question.

When you want a current source:

```text
/askweb what is the current stable Python version?
```

The answer should cite the URLs ATHENA actually retrieved. Small models can still claim they searched when no result section was attached. The system prompt tells them not to.

To use a different model:

```bash
ATHENA_MODEL=qwen2.5:3b python3 scripts/athena_chat.py
```

To quit:

```text
/exit
```

Chat logs are saved automatically in:

```text
logs/chats/
```

## Step 5: Open The Local Page

The terminal can speak replies with `/speak on`. Hearing you from that same terminal needs the Xcode command line tools, because `/listen` runs a small Swift recognizer.

The page is the easier way to talk and to review code:

```bash
python3 scripts/athena_ui.py
```

Use **Listen** for a spoken question and **Speak replies** to hear the answer. Turn on **Documents**, **Web**, or both before you ask. In **Code**, press **Open project** for another folder. Open a file to edit it and press **Save**. Ask ATHENA from the box above the editor. **Apply** writes a reviewed draft. Drag the dividers to resize the file list or the bottom panel, and use **Files** or **Panel** to hide them.

## Step 6: Keep Memory Stable

When using ATHENA on 8 GB:

- Close unused browser tabs
- Quit Docker Desktop unless needed
- Use one local model at a time
- Use the local ATHENA page instead of Open WebUI
- Restart Ollama if the machine feels slow

## Later Upgrade Path

When you move to a machine with 32 GB or more memory, ATHENA can comfortably add:

- Open WebUI
- Chroma or Qdrant for memory and document search
- faster-whisper for voice input
- Piper or another local text-to-speech engine
- Docker Compose services
- Kubernetes and OpenStack tool integrations
