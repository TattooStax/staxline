"""Modem worker core: AT control of the SIM7600 + the call state
machine for the M0a plumbing proof (docs/PLAN.md).

One modem stack on every platform (docs/ARCHITECTURE.md): serial
AT for control, the modem's USB audio device for call audio.
The transport is an interface — SerialTransport in production,
a scripted fake in tests — so the state machine is provable
without hardware and never claims a hardware result it didn't
have.
"""
import re
import time

RING = "RING"
CLIP_RE = re.compile(r'\+CLIP:\s*"([^"]*)"')


class ModemError(Exception):
    pass


class SerialTransport:
    """pyserial-backed transport (pyserial is the modem extra)."""

    def __init__(self, port, baud=115200, timeout=1.0):
        import serial
        self._ser = serial.Serial(port, baud, timeout=timeout)

    def write_line(self, line):
        self._ser.write((line + "\r\n").encode())

    def read_line(self, timeout=30.0):
        self._ser.timeout = timeout
        raw = self._ser.readline()
        if not raw:
            return None
        return raw.decode(errors="replace").strip()

    def close(self):
        self._ser.close()


class Modem:
    def __init__(self, transport):
        self.t = transport

    def command(self, cmd, timeout=10.0, expect="OK"):
        """Send an AT command, collect lines until OK/ERROR."""
        self.t.write_line(cmd)
        lines, deadline = [], time.time() + timeout
        while time.time() < deadline:
            line = self.t.read_line(timeout=max(0.1, deadline - time.time()))
            if line is None:
                break
            if line == "OK":
                return lines
            if line == "ERROR" or line.startswith("+CME ERROR"):
                raise ModemError(f"{cmd} -> {line}")
            if line and line != cmd:  # skip echo
                lines.append(line)
        raise ModemError(f"{cmd} timed out waiting for {expect}")

    def probe(self):
        """Identity + readiness, read-only. Safe on any machine."""
        self.command("AT")
        model = self.command("ATI")
        imei = self.command("AT+CGSN")
        sim = self.command("AT+CPIN?")
        signal = self.command("AT+CSQ")
        return {"model": model, "imei": imei, "sim": sim,
                "signal": signal}

    def wait_for_call(self, timeout=120.0):
        """Block until RING. Returns (rings, caller_number)."""
        rings, number, deadline = 0, None, time.time() + timeout
        while time.time() < deadline:
            line = self.t.read_line(timeout=max(0.1, deadline - time.time()))
            if line is None:
                break
            m = CLIP_RE.search(line or "")
            if m:
                number = m.group(1)
            if line == RING:
                rings += 1
                # Answer promptly: return once the caller is known,
                # or by the second ring if no CLIP ever arrives.
                if number or rings >= 2:
                    return rings, number
        raise ModemError("no incoming call before timeout")

    def answer(self, timeout=20.0):
        """Issue ATA and wait for the modem to confirm the answer
        (OK/CONNECT) or refuse it (NO CARRIER/ERROR)."""
        self.t.write_line("ATA")
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.t.read_line(timeout=max(0.1, deadline - time.time()))
            if line in ("OK", "CONNECT"):
                return
            if line in ("ERROR", "NO CARRIER", "BUSY"):
                raise ModemError(f"ATA -> {line}")
        raise ModemError("ATA timed out waiting for confirmation")

    def hangup(self):
        self.t.write_line("ATH")


def run_m0a_call(modem, audio, db, greeting_wav, record_seconds,
                 out_dir, transcriber=None):
    """One M0a plumbing-proof call (docs/PLAN.md, M0a).

    Ring -> answer -> play the fixed greeting -> record the
    caller -> hang up -> persist the call row. Returns the saved
    call dict. Pass criteria measured here: rings_before_answer,
    time_to_audio_ms. No model is involved in this gate.
    """
    from . import db as dbmod
    started = time.time()
    rings, number = modem.wait_for_call()
    t0 = time.time()
    modem.answer()
    answered = time.time()
    audio.play(greeting_wav)
    # Time from issuing ATA to the modem confirming answer; the
    # greeting starts immediately after. True time-to-first-audio
    # at the caller's ear is a test-day measurement (runbook).
    time_to_audio_ms = int((answered - t0) * 1000)
    rec_path = str(out_dir / f"call-{int(started)}.wav")
    audio.record(rec_path, record_seconds)
    modem.hangup()
    transcript = None
    if transcriber is not None:
        transcript = transcriber(rec_path)
    call = {
        "direction": "in", "number": number, "started_at": started,
        "answered_at": answered, "ended_at": time.time(),
        "answered_by": "m0a-harness", "rings_before_answer": rings,
        "time_to_audio_ms": time_to_audio_ms,
        "recording_path": rec_path, "transcript": transcript,
        "outcome": "answered",
    }
    call["id"] = dbmod.record_call(db, call)
    dbmod.log_activity(db, "m0a",
                       f"M0a call from {number or 'unknown number'}: "
                       f"{rings} ring(s), answered, greeting played, "
                       f"{record_seconds}s recorded.")
    return call
