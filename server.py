import asyncio
from aiohttp import web

from ten_vad import is_speech

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30

async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.BINARY:
                speech = is_speech(msg.data)
                await ws.send_str("1" if speech else "0")
            elif msg.type == web.WSMsgType.ERROR:
                break
    finally:
        await ws.close()
    return ws

def create_app() -> web.Application:
    app = web.Application()
    app.add_routes([web.get('/ws', websocket_handler)])
    return app

if __name__ == '__main__':
    web.run_app(create_app(), port=8000)
