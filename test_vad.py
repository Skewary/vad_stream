import asyncio
import math
import os
import struct
import wave

from aiohttp import web

from server import create_app
from client import stream_file
from non_stream_vad import vad_file


def generate_test_wav(path: str) -> None:
    """Create a simple test wav file if it doesn't already exist."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sr = 16000
    samples = []
    # 0.5 s silence
    samples.extend([0.0] * int(0.5 * sr))
    # 1 s synthetic "voice" (mixture of two sine waves)
    for i in range(int(1 * sr)):
        t = i / sr
        samples.append(
            0.3 * math.sin(2 * math.pi * 200 * t)
            + 0.2 * math.sin(2 * math.pi * 300 * t)
        )
    # 0.5 s silence
    samples.extend([0.0] * int(0.5 * sr))

    ints = [int(max(-1.0, min(1.0, s)) * 32767) for s in samples]
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(b"".join(struct.pack("<h", s) for s in ints))

async def main():
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8000)
    await site.start()

    audio_path = "data/test.wav"
    if not os.path.exists(audio_path):
        generate_test_wav(audio_path)

    stream_results = await stream_file(audio_path)
    non_stream_results = vad_file(audio_path)

    with open("results.txt", "w") as f:
        f.write(f"stream: {stream_results}\n")
        f.write(f"non-stream: {non_stream_results}\n")

    await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main())
