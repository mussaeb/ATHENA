# Vision

Image description is off until you set `ATHENA_VISION_MODEL`.

The default chat model is text-only. A small vision model such as `moondream` can be tried when you have memory to spare. The command is:

```text
/see screenshot.png What error is shown?
```

The script is `scripts/athena_vision.py`. It accepts png, jpg, jpeg, gif, and webp files up to 4 MB.
