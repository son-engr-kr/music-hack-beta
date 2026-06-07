"""Low-latency Magenta RT 2 WebSocket server.

Usage:
    uv run music-hack-beta-server
    # Open http://localhost:8000
"""

import logging
from pathlib import Path
import time

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from music_hack_beta.engine import MRT2Engine, _NOTES_MASKED

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"

engine: MRT2Engine | None = None
app = FastAPI(title="Magenta RT 2 Low-Latency Lab")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")


@app.post("/style/audio")
async def upload_audio_style(file: UploadFile = File(...)):
    assert engine is not None
    assert file.filename is not None
    data = await file.read()
    assert data
    suffix = "." + file.filename.rsplit(".", 1)[-1] if "." in file.filename else ".wav"
    key = engine.set_audio_style(file.filename, suffix, data)
    return {"type": "audio_style", "key": key, "name": file.filename, "bytes": len(data)}


@app.on_event("startup")
async def startup():
    global engine
    logger.info("Initializing Magenta RT 2 engine...")
    engine = MRT2Engine.get_instance()
    logger.info("Engine ready: %s", engine.model_size)


def _parse_notes(msg: dict) -> list[int] | None:
    if msg.get("notes_mode") == "unconditioned":
        return None

    unmask_width = int(msg.get("unmask_width", 0))
    notes = [0] * 128 if unmask_width >= 127 else _NOTES_MASKED[:]
    notes_raw = msg.get("notes")
    if notes_raw is None:
        return notes

    active_pitches = []
    for item in notes_raw:
        assert isinstance(item, list) and len(item) >= 2
        pitch = int(item[0])
        value = int(item[1])
        assert 0 <= pitch < 128
        assert -1 <= value <= 3
        if value > 0:
            active_pitches.append(pitch)

    if 0 < unmask_width < 127:
        for pitch in active_pitches:
            start = max(0, pitch - unmask_width)
            end = min(127, pitch + unmask_width)
            for candidate in range(start, end + 1):
                if notes[candidate] == -1:
                    notes[candidate] = 0

    for item in notes_raw:
        pitch = int(item[0])
        value = int(item[1])
        notes[pitch] = value
    return notes


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    assert engine is not None
    session_id = f"session_{time.time_ns()}"
    logger.info("WebSocket connected: %s", session_id)

    try:
        while True:
            msg = await ws.receive_json()
            action = msg.get("action", "generate")

            if action == "reset":
                engine.reset_session(session_id)
                await ws.send_json({"type": "reset_ack"})
                continue

            assert action == "generate"
            frames = int(msg.get("frames", 1))
            assert 1 <= frames <= 300
            style_sources = msg.get("style_sources")
            style_embedding = engine.get_mixed_style(style_sources) if style_sources else None
            prompt = msg.get("prompt", "synth pad") if msg.get("style_mode", "prompt") == "prompt" and style_embedding is None else None
            notes = _parse_notes(msg)
            drums = msg.get("drums", [-1])

            t0 = time.perf_counter()
            pcm_bytes, sample_rate, samples, channels = engine.generate_pcm32(
                prompt=prompt,
                session_id=session_id,
                notes=notes,
                drums=drums,
                frames=frames,
                temperature=msg.get("temperature"),
                top_k=msg.get("top_k"),
                cfg_musiccoca=msg.get("cfg_musiccoca"),
                cfg_notes=msg.get("cfg_notes"),
                cfg_drums=msg.get("cfg_drums"),
                continuous=bool(msg.get("continuous", True)),
                style_embedding=style_embedding,
            )
            elapsed = time.perf_counter() - t0

            await ws.send_json({
                "type": "audio_meta",
                "sample_rate": sample_rate,
                "channels": channels,
                "samples": samples,
                "frames": frames,
                "generation_seconds": elapsed,
                "ms_per_frame": elapsed / frames * 1000,
                "audio_seconds": samples / sample_rate,
                "payload_bytes": len(pcm_bytes),
            })
            await ws.send_bytes(pcm_bytes)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", session_id)
    finally:
        engine.reset_session(session_id)


def main():
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run(app, host="127.0.0.1", port=port, ws_ping_interval=None)


if __name__ == "__main__":
    main()
