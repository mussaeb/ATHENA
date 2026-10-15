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
- **Code** starts in the ATHENA folder. **Open project** switches to another folder on this computer
- Open a file and edit it in the page. Several files stay open as tabs. **Save** writes your edit. **Apply** writes a draft from ATHENA
- **New file** creates a file in the open folder. Ctrl+P opens a file by name, Ctrl+F finds in the file, and Ctrl+G jumps to a line
- **Ask** clears the box and keeps the recent questions in **Replies**, so a follow-up can refer to the previous one. **Clear** starts that conversation over
- Drag the dividers to resize the file list or the bottom panel. **Files** and **Panel** hide them
- The terminal runs commands you type, starting in the open project

In Chrome, the microphone recognizer sends audio to Google. The answer is still produced by the local model. Safari can use Apple's recognizer instead.

A wake word is intentionally later. This milestone is one button, one utterance.
