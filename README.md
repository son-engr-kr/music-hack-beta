# Music Hack Beta

Live AI music instruments built with Google DeepMind Magenta RealTime 2.

## Requirements

- Apple Silicon Mac
- Python 3.12
- `uv`

## Setup

```bash
uv sync
uv run mrt models init
uv run mrt models download
```

## Run the Web App

```bash
uv run music-hack-beta-server
```

Open http://localhost:8000.

Use a custom port:

```bash
uv run music-hack-beta-server 8001
```

## Run CLI Instruments

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
