"""Audio layer for the modem's USB audio endpoint.

The modem presents call audio as a standard USB audio device.
Real playback/capture uses `sounddevice` (an optional dependency,
provisioned by the installer after it identifies the modem's
audio device). Tests and headless runs use NullAudio, which
writes real WAV files of silence so the recording pipeline —
files, durations, read-back — is exercised honestly without
pretending a human heard anything.
"""
import struct
import wave

SAMPLE_RATE = 16000  # the modem's PCM voice path is 16k


def write_wav(path, frames, rate=SAMPLE_RATE):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)


def tone_wav(path, seconds=2.0, freq=880.0, rate=SAMPLE_RATE):
    """A test-signal WAV. This is a tone, not a voice greeting —
    M0a's gate cares that audio flows, and files must not lie
    about what they contain."""
    import math
    frames = b"".join(
        struct.pack("<h", int(9000 * math.sin(2 * math.pi * freq * i / rate)))
        for i in range(int(seconds * rate)))
    write_wav(path, frames, rate)
    return path


class NullAudio:
    """No real device: play() measures the file, record() writes
    silence of the requested length to a real WAV on disk."""

    def play(self, wav_path):
        with wave.open(str(wav_path), "rb") as w:
            return w.getnframes() / w.getframerate()

    def record(self, wav_path, seconds):
        write_wav(wav_path, b"\x00\x00" * int(seconds * SAMPLE_RATE))
        return wav_path


class SoundDeviceAudio:
    """Real USB audio via sounddevice (optional dependency)."""

    def __init__(self, device=None):
        import sounddevice as sd  # imported late: optional dep
        self._sd = sd
        self.device = device

    def play(self, wav_path):
        import soundfile as sf
        data, rate = sf.read(str(wav_path), dtype="int16")
        self._sd.play(data, rate, device=self.device)
        self._sd.wait()
        return len(data) / rate

    def record(self, wav_path, seconds):
        frames = self._sd.rec(int(seconds * SAMPLE_RATE),
                               samplerate=SAMPLE_RATE, channels=1,
                               dtype="int16", device=self.device)
        self._sd.wait()
        write_wav(wav_path, frames.tobytes())
        return wav_path
