#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import tornado.ioloop
import tornado.web
import tornado.websocket
import soundfile as sf
import sherpa_onnx


class VADSession:
    def __init__(self,
                 model_path="ten-vad.onnx",
                 frame_ms=30,
                 sample_rate=16000,
                 speech_threshold=0.5,
                 min_speech_duration=0.3,
                 min_silence_duration=0.5):
        """
        Sherpa-ONNX VAD Session
        """
        self.vad = sherpa_onnx.Vad(model=model_path,
                                   sample_rate=sample_rate,
                                   frame_ms=frame_ms)
        self.sr = sample_rate
        self.frame_ms = frame_ms
        self.frame_samples = self.sr * self.frame_ms // 1000
        self.speech_threshold = speech_threshold

        # 缓冲区
        self.in_segment = False
        self.current_buffer = []
        self.speech_segments = []

        # 工程化参数
        self.min_speech_frames = int(min_speech_duration * self.sr / self.frame_samples)
        self.min_silence_frames = int(min_silence_duration * self.sr / self.frame_samples)
        self.silence_count = 0

    def push_frame(self, frame_bytes):
        """
        输入一帧 PCM16 (bytes)，内部缓存拼接语音段
        """
        frame = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        score = self.vad.forward(frame)  # float 概率
        is_speech = score > self.speech_threshold

        if not self.in_segment:
            if is_speech:
                self.in_segment = True
                self.current_buffer = [frame]
        else:
            if is_speech:
                self.current_buffer.append(frame)
                self.silence_count = 0
            else:
                self.silence_count += 1
                if self.silence_count > self.min_silence_frames:
                    # 结束一个语音段
                    if len(self.current_buffer) >= self.min_speech_frames:
                        wav = np.concatenate(self.current_buffer, axis=0)
                        self.speech_segments.append(wav)
                    self.in_segment = False
                    self.current_buffer = []

    def flush(self):
        """
        返回拼接的人声段 PCM16
        """
        if self.in_segment and len(self.current_buffer) >= self.min_speech_frames:
            wav = np.concatenate(self.current_buffer, axis=0)
            self.speech_segments.append(wav)
        self.in_segment = False
        self.current_buffer = []

        if not self.speech_segments:
            return None

        all_wav = np.concatenate(self.speech_segments, axis=0)
        pcm16 = (all_wav * 32767).astype(np.int16)
        return pcm16


# ---------------- Tornado WebSocket ---------------- #

class VADWebSocket(tornado.websocket.WebSocketHandler):
    def open(self):
        print("WebSocket opened")
        self.session = VADSession(model_path="ten-vad.onnx")

    def on_message(self, message):
        # 每次 message 应该是一个 PCM16 帧
        self.session.push_frame(message)

    def on_close(self):
        print("WebSocket closed")
        wav_pcm16 = self.session.flush()
        if wav_pcm16 is not None:
            # 直接返回二进制 wav
            import io
            buf = io.BytesIO()
            sf.write(buf, wav_pcm16, self.session.sr, format="WAV")
            self.write_message(buf.getvalue(), binary=True)


def make_app():
    return tornado.web.Application([
        (r"/ws/vad", VADWebSocket),
    ])


if __name__ == "__main__":
    app = make_app()
    app.listen(9001)
    print("Sherpa-ONNX TenVad WebSocket 服务启动: ws://localhost:9001/ws/vad")
    tornado.ioloop.IOLoop.current().start()
