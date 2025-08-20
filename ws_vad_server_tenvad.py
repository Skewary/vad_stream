# ws_vad_server_tenvad.py
# -*- coding: utf-8 -*-
"""
WebSocket 流式 VAD 服务（优先 tenVAD，回退 WebRTC VAD）
- 地址：ws://<host>:<port>/ws/vad
- 输入：客户端以二进制发送定长帧（16kHz, mono, PCM16），默认 10ms/帧（320字节）
- 输出：
  * JSON 事件：segment_start / segment_end / segment_discard / ready / error / pong
  * 二进制音频：仅当该帧被视作“语音”时，返回以 b'\\xAA\\x01' 前缀的 PCM16 帧（可直接拼接）
环境变量（可选）：
  VAD_WS_PORT=5780
  VAD_SR=16000
  VAD_FRAME_MS=10            # 10 或 16（tenVAD 推荐 hop 160 或 256）
  VAD_HANGOVER_MS=200        # 结束前保留静音（防断裂）
  VAD_MIN_SEG_MS=150         # 过短段丢弃
  VAD_AGGR=3                 # WebRTC 激进度 0~3
"""

import os
import json
import time
import struct

import tornado.web
import tornado.ioloop
import tornado.websocket

# ---------- 可选 tenVAD 适配 ----------
_TENVAD_AVAILABLE = False
_tenvad_adapter = None
try:
    import tenvad  # 你们的包名/模块名，若不同请改这里
    _TENVAD_AVAILABLE = True
except Exception:
    _TENVAD_AVAILABLE = False

import webrtcvad  # 作为回退

# ----------- 配置 -----------
SAMPLE_RATE = int(os.environ.get("VAD_SR", "16000"))
FRAME_MS = int(os.environ.get("VAD_FRAME_MS", "10"))  # 10 或 16
BYTES_PER_SAMPLE = 2
SAMPLES_PER_FRAME = SAMPLE_RATE * FRAME_MS // 1000
BYTES_PER_FRAME = SAMPLES_PER_FRAME * BYTES_PER_SAMPLE

VAD_AGGR = int(os.environ.get("VAD_AGGR", "3"))
HANGOVER_MS = int(os.environ.get("VAD_HANGOVER_MS", "200"))
MIN_SEG_MS = int(os.environ.get("VAD_MIN_SEG_MS", "150"))

MAGIC_AUDIO_PREFIX = b"\xAA\x01"  # 用于区分二进制“语音帧”

# ----------- tenVAD 适配器 -----------
class TenVADAdapter(object):
    """
    兼容不同发行形态：
    - model.is_speech(frame_bytes) -> bool
    - model.forward(frame_xxx)     -> bool/概率/分数
    若 forward 需要 float32[-1,1]，这里做 bytes->float32 的转换。
    """
    def __init__(self):
        # 优先常见构造方式
        self.model = None
        # 1) 直接类
        if hasattr(tenvad, "VAD"):
            try:
                self.model = tenvad.VAD()
            except Exception:
                self.model = None
        # 2) 工厂/加载
        if self.model is None and hasattr(tenvad, "load"):
            try:
                self.model = tenvad.load()
            except Exception:
                self.model = None

        if self.model is None:
            # 留给用户自定义：如果你们库的入口不同，可在此处补充
            raise RuntimeError("tenVAD: 未找到可用的构造方式（尝试 VAD()/load() 失败）")

        self.has_is_speech = hasattr(self.model, "is_speech")
        self.has_forward = hasattr(self.model, "forward")

        if not (self.has_is_speech or self.has_forward):
            raise RuntimeError("tenVAD: 既无 is_speech 也无 forward 方法")

    @staticmethod
    def pcm16_bytes_to_float32(frame_bytes):
        # 小端有符号16位整数 -> float32 [-1,1]
        import numpy as np
        arr = np.frombuffer(frame_bytes, dtype="<i2").astype("float32")
        # 避免除零
        return (arr / 32767.0).clip(-1.0, 1.0)

    def is_speech(self, frame_bytes):
        # 优先直接 is_speech(bytes)
        if self.has_is_speech:
            try:
                ret = self.model.is_speech(frame_bytes)
                # 兼容返回概率/分数
                if isinstance(ret, bool):
                    return ret
                try:
                    return float(ret) > 0.5
                except Exception:
                    return bool(ret)
            except Exception:
                pass

        # 其次 forward(...)：可能需要 float32
        if self.has_forward:
            try:
                # 先尝试直接 bytes
                ret = self.model.forward(frame_bytes)
                if isinstance(ret, bool):
                    return ret
                try:
                    return float(ret) > 0.5
                except Exception:
                    pass
            except Exception:
                # 再尝试 float32
                try:
                    x = self.pcm16_bytes_to_float32(frame_bytes)
                    ret = self.model.forward(x)
                    if isinstance(ret, bool):
                        return ret
                    try:
                        return float(ret) > 0.5
                    except Exception:
                        return bool(ret)
                except Exception:
                    pass

        # 都失败则视作非语音
        return False

# ----------- 会话 -----------
class VADSession(object):
    def __init__(self):
        self.sr = SAMPLE_RATE
        self.frame_ms = FRAME_MS
        self.frame_bytes = BYTES_PER_FRAME
        self.hangover_frames = max(0, HANGOVER_MS // FRAME_MS)
        self.min_seg_frames = max(1, MIN_SEG_MS // FRAME_MS)

        self.backend = "tenvad" if _TENVAD_AVAILABLE else "webrtcvad"
        self.tenvad = None
        if self.backend == "tenvad":
            try:
                self.tenvad = TenVADAdapter()
            except Exception:
                self.backend = "webrtcvad"
                self.tenvad = None

        self.wrvad = webrtcvad.Vad(VAD_AGGR) if self.backend == "webrtcvad" else None

        self.in_voice = False
        self.seg_start_ms = 0
        self.cur_time_ms = 0
        self.sil_count = 0
        self.voice_frames = []  # 当前段缓存

    def _is_speech(self, frame_bytes):
        if self.backend == "tenvad" and self.tenvad is not None:
            return self.tenvad.is_speech(frame_bytes)
        # webrtcvad 回退
        return self.wrvad.is_speech(frame_bytes, self.sr)

    def push_frame(self, frame_bytes):
        """
        返回：(events, audio_bytes)
        - events: [ {type: segment_start|segment_end|segment_discard, ...}, ... ]
        - audio_bytes: 若此帧归入“语音拼接流”，返回该帧 PCM16；否则 b""
        """
        assert len(frame_bytes) == self.frame_bytes, "bad frame size"
        events = []
        out_audio = b""

        is_speech = self._is_speech(frame_bytes)
        if is_speech:
            self.sil_count = 0
            if not self.in_voice:
                self.in_voice = True
                self.seg_start_ms = self.cur_time_ms
                events.append({"type": "segment_start", "ts_ms": self.seg_start_ms, "backend": self.backend})
            out_audio = frame_bytes
            self.voice_frames.append(frame_bytes)
        else:
            if self.in_voice:
                self.sil_count += 1
                if self.sil_count <= self.hangover_frames:
                    # hangover 内仍计入语音，平滑收尾
                    out_audio = frame_bytes
                    self.voice_frames.append(frame_bytes)
                else:
                    # 结束一个段落
                    frames_len = len(self.voice_frames)
                    if frames_len >= self.min_seg_frames:
                        dur_ms = frames_len * self.frame_ms
                        events.append({"type": "segment_end", "ts_ms": self.cur_time_ms, "dur_ms": dur_ms})
                    else:
                        # 过短段丢弃
                        events.append({"type": "segment_discard", "ts_ms": self.cur_time_ms})
                    self.voice_frames = []
                    self.in_voice = False
                    self.sil_count = 0

        self.cur_time_ms += self.frame_ms
        return events, out_audio

    def flush(self):
        events = []
        if self.in_voice:
            frames_len = len(self.voice_frames)
            if frames_len >= self.min_seg_frames:
                dur_ms = frames_len * self.frame_ms
                events.append({"type": "segment_end", "ts_ms": self.cur_time_ms, "dur_ms": dur_ms})
            else:
                events.append({"type": "segment_discard", "ts_ms": self.cur_time_ms})
        return events

# ----------- WebSocket Handler -----------
class VADSocket(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True  # 生产请按需限制

    def open(self):
        self.session = VADSession()
        self.write_message({
            "type": "ready",
            "sr": SAMPLE_RATE,
            "frame_ms": FRAME_MS,
            "bytes_per_frame": BYTES_PER_FRAME,
            "backend": self.session.backend
        })

    def on_message(self, message):
        # 二进制：音频帧；文本：JSON 控制
        if isinstance(message, bytes):
            if len(message) != BYTES_PER_FRAME:
                self.write_message({"type": "error", "msg": "frame size must be %d, got %d" % (BYTES_PER_FRAME, len(message))})
                return
            try:
                events, pcm = self.session.push_frame(message)
            except AssertionError as e:
                self.write_message({"type": "error", "msg": str(e)})
                return
            except Exception as e:
                self.write_message({"type": "error", "msg": "push_frame failed: %s" % str(e)})
                return

            for ev in events:
                self.write_message(ev)

            if pcm:
                self.write_message(MAGIC_AUDIO_PREFIX + pcm, binary=True)

        else:
            # JSON 控制（可扩展：切换后端、参数、ping 等）
            try:
                obj = json.loads(message)
            except Exception:
                self.write_message({"type": "error", "msg": "bad json"})
                return

            t = obj.get("type")
            if t == "ping":
                self.write_message({"type": "pong"})
            elif t == "set":
                # 仅演示提示，实际动态修改需要重建 session
                self.write_message({"type": "warn", "msg": "动态修改参数尚未实现，请在重连前通过环境变量设置"})
            else:
                self.write_message({"type": "warn", "msg": "unknown control msg"})

    def on_close(self):
        if hasattr(self, "session"):
            for ev in self.session.flush():
                try:
                    self.write_message(ev)
                except Exception:
                    pass

class Health(tornado.web.RequestHandler):
    def get(self):
        self.write({"status": "ok"})

def make_app():
    return tornado.web.Application([
        (r"/health", Health),
        (r"/ws/vad", VADSocket),
    ])

if __name__ == "__main__":
    port = int(os.environ.get("VAD_WS_PORT", "5780"))
    app = make_app()
    app.listen(port)
    print("[ws-vad] listening on ws://0.0.0.0:%d/ws/vad  (SR=%d, frame=%dms, backend=%s)" %
          (port, SAMPLE_RATE, FRAME_MS, "tenVAD" if _TENVAD_AVAILABLE else "webrtcvad"))
    tornado.ioloop.IOLoop.current().start()
