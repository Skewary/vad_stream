# -*- coding: utf-8 -*-
"""测试 TEN VAD 的 HTTP 与 WebSocket 接口"""

import os
import time
import subprocess
import requests
import websocket
import soundfile as sf
import numpy as np
import matplotlib.pyplot as plt

AUDIO_URL = "https://paddlespeech.bj.bcebos.com/PaddleAudio/zh.wav"
AUDIO_FILE = "input.wav"


def download_audio():
    """下载测试音频"""
    if os.path.exists(AUDIO_FILE):
        return
    resp = requests.get(AUDIO_URL)
    resp.raise_for_status()
    with open(AUDIO_FILE, "wb") as f:
        f.write(resp.content)


def start_server():
    """后台启动 Tornado 服务"""
    return subprocess.Popen(["python", "server.py"], stdout=subprocess.DEVNULL)


def test_http(path):
    url = "http://localhost:8002/vad"
    with open(path, "rb") as f:
        resp = requests.post(url, files={"file": f})
    if resp.status_code == 200:
        out = "speech_http.wav"
        with open(out, "wb") as f:
            f.write(resp.content)
        return out
    return None


def test_ws(path):
    out_file = "speech_ws.wav"
    audio, sr = sf.read(path, dtype="int16")
    frame_size = int(sr * 0.01)
    done = {"ok": False}

    def on_message(ws, message):
        if isinstance(message, bytes):
            with open(out_file, "wb") as f:
                f.write(message)
            done["ok"] = True
            ws.close()

    def on_open(ws):
        for i in range(0, len(audio), frame_size):
            frame = audio[i : i + frame_size]
            ws.send(frame.tobytes(), opcode=websocket.ABNF.OPCODE_BINARY)
        ws.send("FLUSH")

    ws = websocket.WebSocketApp(
        "ws://localhost:8002/vad/ws", on_message=on_message, on_open=on_open
    )
    ws.run_forever()
    return out_file if done["ok"] else None


def save_results(results):
    with open("results.txt", "w") as f:
        for name, path in results.items():
            if path and os.path.exists(path):
                data, sr = sf.read(path)
                f.write(f"{name}: {len(data) / sr:.2f}s\n")
            else:
                f.write(f"{name}: no_voice\n")


def plot_comparison(orig_path, http_path, ws_path):
    orig, sr = sf.read(orig_path)
    http, _ = sf.read(http_path)
    ws, _ = sf.read(ws_path)

    plt.figure(figsize=(10, 6))
    t = np.linspace(0, len(orig) / sr, len(orig))
    plt.subplot(3, 1, 1)
    plt.title("Original")
    plt.plot(t, orig)

    t2 = np.linspace(0, len(http) / sr, len(http))
    plt.subplot(3, 1, 2)
    plt.title("HTTP VAD")
    plt.plot(t2, http)

    t3 = np.linspace(0, len(ws) / sr, len(ws))
    plt.subplot(3, 1, 3)
    plt.title("WebSocket VAD")
    plt.plot(t3, ws)

    plt.tight_layout()
    plt.savefig("comparison.png")


if __name__ == "__main__":
    download_audio()
    proc = start_server()
    time.sleep(1)
    try:
        http_out = test_http(AUDIO_FILE)
        ws_out = test_ws(AUDIO_FILE)
        save_results({"http": http_out, "ws": ws_out})
        if http_out and ws_out:
            plot_comparison(AUDIO_FILE, http_out, ws_out)
    finally:
        proc.terminate()
        proc.wait()

