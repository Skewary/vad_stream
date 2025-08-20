import array

THRESHOLD = 500  # average absolute amplitude threshold


def is_speech(frame: bytes, threshold: int = THRESHOLD) -> bool:
    """Simple time-domain energy VAD.

    Converts 16-bit PCM bytes to samples, computes the average absolute
    amplitude, and compares it against a fixed threshold.
    """
    if not frame:
        return False
    samples = array.array('h')
    samples.frombytes(frame)
    avg_amp = sum(abs(s) for s in samples) / len(samples)
    return avg_amp > threshold
