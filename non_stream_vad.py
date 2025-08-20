import wave

from ten_vad import is_speech

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30


def vad_file(path: str):
    with wave.open(path, 'rb') as wf:
        if wf.getframerate() != SAMPLE_RATE:
            raise ValueError('Only 16kHz files supported')
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
            raise ValueError('Require 16-bit mono PCM WAV')
        frame_bytes = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000) * wf.getsampwidth()
        results = []
        while True:
            data = wf.readframes(frame_bytes // wf.getsampwidth())
            if len(data) < frame_bytes:
                break
            results.append(is_speech(data))
        return results

if __name__ == '__main__':
    import sys
    print(vad_file(sys.argv[1]))
