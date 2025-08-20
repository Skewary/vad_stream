#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import io
import wave
import json
import numpy as np
import soundfile as sf
import librosa
import tornado.ioloop
import tornado.web
import tornado.websocket
from ten_vad import TenVad  # ✅ TenVad 引擎

# ============== VAD Session ==============
class VADSession:
    def __init__(self, sr=16000, frame_ms=10,
                 start_min_speech_ms=200, end_min_silence_ms=300,
                 min_chunk_ms=200, pad_ms=80):
        self.vad = TenVad()
        self.sr = sr
        self.frame_ms = frame_ms
        self.frame_size = sr * frame_ms // 1000
        self.frame_bytes = self.frame_size * 2  # int16
        # 工程化参数
        self.start_frames = start_min_speech_ms // frame_ms
        self.end_frames = end_min_silence_ms // frame_ms
        self.min_chunk_frames = min_chunk_ms // frame_ms
        self.pad_frames = pad_ms // frame_ms

        self.reset()

    def reset(self):
        self.in_segment = False
        self.buffer = []
        self.segment_frames = []
        self.silence_count = 0
        self.output_segments = []

    def push_frame(self, frame_bytes):
        """输入一帧 int16 PCM16，返回 segment 事件或 None"""
        is_speech = self.vad.is_speech(frame_bytes)
        self.buffer.append(np.frombuffer(frame_bytes, dtype=np.int16))

        if not self.in_segment:
            # 起段检测
            self.segment_frames.append(is_speech)
            if len(self.segment_frames) >= self.start_frames and all(self.segment_frames[-self.start_frames:]):
                self.in_segment = True
                self.segment_audio = self.buffer[-self.start_frames:]
                self.segment_frames = []
        else:
            # 已在段内
            if is_speech:
                self.segment_audio.append(np.frombuffer(frame_bytes, dtype=np.int16))
                self.silence_count = 0
            else:
                self.silence_count += 1
                if self.silence_count >= self.end_frames:
                    # 收段
                    audio_arr = np.concatenate(self.segment_audio)
                    if len(audio_arr) >= self.min_chunk_frames * self.frame_size:
                        self.output_segments.append(audio_arr)
                    self.in_segment = False
                    self.segment_audio = []
                    self.silence_count = 0

    def flush(self):
        """输出最终拼接后的音频"""
        if self.in_segment and len(self.segment_audio) > 0:
            audio_arr = np.concatenate(self.segment_audio)
            if len(audio_arr) >= self.min_chunk_frames * self.frame_size:
                self.output_segments.append(audio_arr)

        if not self.output_segments:
            return None

        audio_concat = np.concatenate(self.output_segments)
        buf = io.BytesIO()
        sf.write(buf, audio_concat, self.sr, format="WAV")
        buf.seek(0)
        return buf.read()


# ============== HTTP 接口 ==============
class VADHandler(tornado.web.RequestHandler):
    def post(self):
        """上传音频文件，返回拼接后的人声音频"""
        file_body = self.request.files['file'][0]['body']
        # 读音频，转 16k
        audio, sr = librosa.load(io.BytesIO(file_body), sr=16000, mono=True)
        int16_audio = (audio * 32767).astype(np.int16)

        session = VADSession(sr=16000)
        for i in range(0, len(int16_audio), session.frame_size):
            frame = int16_audio[i:i+session.frame_size]
            if len(frame) < session.frame_size:
                break
            session.push_frame(frame.tobytes())

        wav_bytes = session.flush()
        if wav_bytes is None:
            self.set_status(204)
            return
        self.set_header("Content-Type", "audio/wav")
        self.write(wav_bytes)


# ============== WebSocket 接口 ==============
class VADWebSocket(tornado.websocket.WebSocketHandler):
    def open(self):
        self.session = VADSession()
        print("WebSocket opened")

    def on_message(self, message):
        if message == "FLUSH":
            wav_bytes = self.session.flush()
            if wav_bytes:
                self.write_message({"event": "final"})
                self.write_message(wav_bytes, binary=True)
            else:
                self.write_message({"event": "no_voice"})
            return

        # 默认收到的是 PCM16 帧
        self.session.push_frame(message)

    def on_close(self):
        print("WebSocket closed")


# ============== 主程序入口 ==============
def make_app():
    return tornado.web.Application([
        (r"/vad", VADHandler),
        (r"/vad/ws", VADWebSocket),
    ])

if __name__ == "__main__":
    app = make_app()
    app.listen(8002)
    print("✅ VAD 服务启动成功: http://localhost:8002/vad")
    tornado.ioloop.IOLoop.current().start()
