"""Audio layer for the modem's USB audio endpoint.

The modem presents call audio as a standard USB audio device.
Real playback/capture uses `sounddevice` (an optional dependency,
provisioned by the installer after it identifies the modem's
audio device). Tests and headless runs use NullAudio, which
writes real WAV files of silence so the recording pipeline —
files, durations, read-back — is exercised honestly without
pretending a human heard anything.
"""
import os
import struct
import time
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


def melody_wav(path, notes=(523.25, 659.25, 783.99), seconds=0.35,
               rate=SAMPLE_RATE):
    """A short sequence of distinct tones: the TX test signal.
    If the caller hears these notes in order, transmit audio is
    flowing cleanly; if they hear a steady buzz instead, the
    path is starving. A test signal, not a voice."""
    import math
    frames = bytearray()
    for freq in notes:
        frames += b"".join(
            struct.pack("<h", int(9000 * math.sin(
                2 * math.pi * freq * i / rate)))
            for i in range(int(seconds * rate)))
    write_wav(path, bytes(frames), rate)
    return path


class PcmStream:
    """Full-duplex paced PCM over the modem's USB audio endpoint.

    One frame every `frame_ms`: queued speech if any is waiting,
    silence otherwise. The write side is fed on schedule whether
    or not there is anything to say, because a starved transmit
    path is what looped a single frame into a continuous ~85 Hz
    buzz on the 2026-11-03 live call — the modem repeats its
    last frame when the host stops feeding it. Silence is data
    here: it is what keeps the line honest while the agent is
    listening.

    `pump_once()` is the whole mechanism and is directly
    testable with a fake fd; `run()` is the paced loop the live
    worker drives on its own thread.
    """

    def __init__(self, fd, rate=SAMPLE_RATE, frame_ms=20):
        self.fd = fd
        self.rate = rate
        self.frame_bytes = int(rate * frame_ms / 1000) * 2
        self._outbox = bytearray()
        self.captured = bytearray()
        self._silence = b"\x00" * self.frame_bytes

    def queue_pcm(self, frames):
        self._outbox += frames

    def queue_wav(self, path):
        with wave.open(str(path), "rb") as w:
            if w.getframerate() != self.rate or w.getsampwidth() != 2:
                raise ValueError(
                    "wav must be 16-bit at the stream rate")
            self.queue_pcm(w.readframes(w.getnframes()))

    def pump_once(self):
        """Capture what is available; write exactly one frame."""
        try:
            chunk = self.fd.read(8192)
            if chunk:
                self.captured += chunk
        except BlockingIOError:
            pass
        if len(self._outbox) >= self.frame_bytes:
            frame = bytes(self._outbox[:self.frame_bytes])
            del self._outbox[:self.frame_bytes]
        elif self._outbox:
            frame = bytes(self._outbox) + self._silence[
                len(self._outbox):]
            self._outbox.clear()
        else:
            frame = self._silence
        self.fd.write(frame)
        return frame

    def run(self, seconds, clock=time.monotonic, sleep=time.sleep):
        """Pace pump_once() for `seconds` of wall time."""
        deadline = clock() + seconds
        frame_s = self.frame_bytes / 2 / self.rate
        while clock() < deadline:
            t0 = clock()
            self.pump_once()
            sleep(max(0.0, frame_s - (clock() - t0)))


class OsPcmFd:
    """The modem's audio endpoint as a file-style duplex fd.
    Reads are nonblocking and return b'' when nothing has
    arrived yet — the pump treats an empty read as a normal
    frame interval, not an error."""

    def __init__(self, path):
        self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)

    def read(self, n):
        try:
            return os.read(self.fd, n)
        except BlockingIOError:
            return b""

    def write(self, data):
        return os.write(self.fd, data)

    def close(self):
        os.close(self.fd)


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
