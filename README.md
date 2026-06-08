# MuseHub Challenge 2026 - 1st place

# UNREALTIME

Live AI music instruments built with Google DeepMind Magenta RealTime 2.

Turn rough musical ideas into playable instruments: prompt a sound, play it,
record a loop, clone the loop, and play the cloned vibe again.

- Demo video: https://www.youtube.com/watch?v=M8jCCZiL7YM
- Event page: https://musichackspace.org/events/hackathon-boston-june-2026
- Hackathon: Music Technology Hackathon: Build the Future of Creative Tools
- Location: Berklee College of Music, Boston

---

## Table of contents

- What UNREALTIME does
- Workflow
- Architecture
- Tech stack
- Repository layout
- Local development
- CLI instruments
- Hackathon context

---

## What UNREALTIME does

UNREALTIME is a fast music prototyping workflow for building playable sounds.

Instead of searching for the perfect sample or manually tuning a plugin forever,
the user can:

1. Generate a playable VST-like instrument from prompts.
2. Mix multiple prompt sources with weighted prompt controls.
3. Play the instrument with MIDI or computer keyboard input.
4. Record rough performances into a loop station.
5. Clone the messy loop back into a new playable sound.

The goal is not a perfect final mix. The goal is to catch the vibe quickly and
keep playing.

---

## Workflow

```text
Prompt mix
    |
    v
Playable instrument
    |
    v
Loop station
    |
    v
Messy loop
    |
    v
Clone current loop
    |
    v
New playable instrument
```

The hackathon pitch also used a Suno-generated presentation song instead of a
traditional spoken narration.

---

## Architecture

```text
Browser UI
  |-- Generation panel
  |   |-- Prompt mode
  |   |-- Node / weighted prompt mix mode
  |   `-- Clone mode
  |
  |-- Note input
  |   |-- MIDI keyboard
  |   `-- Computer keyboard
  |
  `-- Loop station
      |-- Track recording
      |-- Loop playback
      |-- State save / load
      `-- Clone current loop

FastAPI server
  `-- Magenta RealTime 2 / MLX engine
```

---

## Tech stack

| Layer | Technology |
| --- | --- |
| Model | Google DeepMind Magenta RealTime 2 |
| Runtime | MLX on Apple Silicon |
| Backend | FastAPI, Uvicorn |
| Frontend | Static browser UI, Web Audio worklet |
| Package manager | uv |
| Language | Python 3.12, JavaScript |

---

## Repository layout

```text
.
|-- src/music_hack_beta/
|   |-- server.py              FastAPI web server
|   |-- engine.py              Magenta RealTime 2 engine wrapper
|   |-- cli.py                 CLI entrypoint
|   |-- jam.py                 Live jam command
|   |-- synth.py               Prompt instrument command
|   |-- gesture.py             Gesture-style instrument command
|   |-- looper.py              Loop-oriented command
|   `-- static/
|       |-- index.html         Browser UI
|       `-- audio-worklet.js   Low-latency browser audio path
|-- pyproject.toml
|-- uv.lock
`-- README.md
```

---

## Local development

### Requirements

- Apple Silicon Mac
- Python 3.12
- `uv`

### Setup

```bash
uv sync
uv run mrt models init
uv run mrt models download
```

### Run the web app

```bash
uv run music-hack-beta-server
```

Open http://localhost:8000.

Use a custom port:

```bash
uv run music-hack-beta-server 8001
```

---

## CLI instruments

```bash
uv run music-hack-beta jam --style "jazz quartet"
uv run music-hack-beta synth --prompt "warm analog pad"
uv run music-hack-beta gesture --style "synthwave lead"
uv run music-hack-beta looper --style "lofi hip hop"
```

The legacy example command name is also available:

```bash
uv run mrt2-jam synth --prompt "warm analog pad"
```

---

## Hackathon context

UNREALTIME won 1st place in the MuseHub Challenge at the Music Technology
Hackathon: Build the Future of Creative Tools, held June 6-7, 2026 at Berklee
College of Music.

The challenge asked teams to build creative music products with a path toward
publication and distribution through the MuseHub ecosystem.
