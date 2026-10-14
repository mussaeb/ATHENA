# Milestone 6: Voice

ATHENA can read replies aloud, take one spoken question, and do both from the local page.

## Hear Replies

```text
/speak on
/say The local model is ready.
/speak off
```

You can also start a session with speech already on:

```bash
ATHENA_SPEAK=on python3 scripts/athena_chat.py
```

The voice comes from the operating system:

- macOS uses `say`
- Windows uses the built-in speech synthesizer
- Other systems use `espeak-ng` or `espeak` when that command is installed

Code blocks are left out of the spoken text.

## Push To Talk

```text
/listen
```

ATHENA listens once, prints what it heard, and answers that text. Speak, then pause.

- Windows uses the built-in speech recognizer
- macOS uses on-device recognition through `scripts/athena_listen_mac.swift` when the Swift command is installed. The first run asks for microphone and speech-recognition permission for Terminal
- Other systems keep keyboard input

If listening is unavailable, the message says so and the keyboard still works.

## Local Page

```bash
python3 scripts/athena_ui.py
```

Open http://127.0.0.1:8765 if it does not open on its own.

- **Listen** uses the browser microphone and sends that sentence as the question
- **Speak replies** reads the answer with the operating system voice
- **Documents** and **Web** attach those sources to ordinary questions
- **Code** browses project folders and files, asks ATHENA to work in the open folder or the whole project, and writes a file only after **Apply**
- The terminal at the bottom runs commands you type, starting in the project folder

In Chrome, the microphone recognizer sends audio to Google. The answer is still produced by the local model. Safari can use Apple's recognizer instead.

A wake word is intentionally later. This milestone is one button, one utterance.
