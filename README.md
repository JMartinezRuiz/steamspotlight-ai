# SteamSpotlight AI

SteamSpotlight AI is a Python pipeline that finds recent Steam releases, ranks them with public signals, generates short video scripts with AI, creates narration, and renders a vertical video for short-form platforms.

## What it does

- Scrapes recent Steam releases for a date range.
- Enriches each game with Steam page metadata, media, reviews, tags, and pricing.
- Scores games with review data, Twitch traction, and Steam momentum.
- Uses OpenAI to generate intro, game, and outro scripts.
- Uses ElevenLabs or local TTS to generate narration.
- Renders a vertical video with ranking overlays, captions, gameplay media, and intro/outro sections.

## Requirements

- Python 3.10+
- FFmpeg support through MoviePy/imageio-ffmpeg
- API credentials configured as environment variables

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables

Copy `.env.example` to your local environment manager or configure these variables in your shell:

```bash
OPENAI_API_KEY=
TWITCH_CLIENT_ID=
TWITCH_CLIENT_SECRET=
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
STEAM_VIDEO_OUTPUT=video_final.mp4
```

Generated videos, downloaded game media, logs, and the local SQLite database are intentionally ignored by Git.

## Example

```bash
python main.py "12 JUN 2026" "15 JUN 2026" 3 --elevenlabsnarrator --model gpt-4o-mini --max 20
```

For faster local validation renders:

```bash
set STEAM_VIDEO_RESOLUTION=540x960
set STEAM_VIDEO_FPS=8
set STEAM_VIDEO_BACKGROUND=cover
set STEAM_VIDEO_PRESET=ultrafast
python main.py "12 JUN 2026" "15 JUN 2026" 3 --elevenlabsnarrator --model gpt-4o-mini --max 8
```

## Notes

This project stores runtime data in `SR_BBDD.db` and generated media under `currentgames/`. Those files are not part of the repository because they can be large, regenerated, and may include third-party media from Steam pages.
