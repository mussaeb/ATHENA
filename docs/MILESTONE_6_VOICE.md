# Milestone 6: Voice

ATHENA can read replies aloud and take one spoken question on Windows.

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

On Windows:

```text
/listen
```

ATHENA listens once, prints what it heard, and answers that text. Speak, then pause. If the speech recognizer is not installed, the message says so and the keyboard still works.

macOS and Linux keep text input for questions. `/speak on` can still read the reply when a local voice command exists.

A wake word is intentionally later. This milestone is one button, one utterance.
