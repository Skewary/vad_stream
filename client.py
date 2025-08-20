import asyncio
import wave
from aiohttp import ClientSession

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30

async def stream_file(path: str, url: str = 'http://localhost:8000/ws'):
    frame_size = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)
    with wave.open(path, 'rb') as wf:
        if wf.getframerate() != SAMPLE_RATE:
            raise ValueError('Only 16kHz files supported')
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
            raise ValueError('Require 16-bit mono PCM WAV')
        async with ClientSession() as session:
            async with session.ws_connect(url) as ws:
                results = []
                while True:
                    data = wf.readframes(frame_size)
                    if len(data) < frame_size * wf.getsampwidth():
                        break
                    await ws.send_bytes(data)
                    msg = await ws.receive()
                    if msg.type == 1:  # text
                        results.append(msg.data)
                return results

if __name__ == '__main__':
    import sys
    asyncio.run(stream_file(sys.argv[1]))
