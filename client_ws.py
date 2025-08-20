import websocket
import soundfile as sf

def stream_audio(ws, audio_path):
    audio, sr = sf.read(audio_path, dtype="int16")
    assert sr == 16000, "需要 16kHz 音频"

    frame_size = int(sr * 0.01)  # 10ms
    for i in range(0, len(audio), frame_size):
        frame = audio[i:i+frame_size]
        ws.send(frame.tobytes(), opcode=websocket.ABNF.OPCODE_BINARY)

    ws.send("FLUSH")  # 通知服务端收尾

def on_message(ws, message):
    if isinstance(message, bytes):
        with open("speech_ws.wav", "wb") as f:
            f.write(message)
        print("✅ WebSocket 人声音频保存到 speech_ws.wav")
    else:
        print("收到消息:", message)

def on_open(ws):
    print("WebSocket 连接成功")
    stream_audio(ws, "input.wav")

ws = websocket.WebSocketApp("ws://localhost:8002/vad/ws",
                            on_message=on_message,
                            on_open=on_open)
ws.run_forever()
