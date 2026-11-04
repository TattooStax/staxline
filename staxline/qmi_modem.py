"""Linux modem worker: the transport binding the live evidence
chose (docs/evidence/2026-11-03-victus-live-test.md).

Two bindings, because the hardware split the work that way:

- ModemManager (via mmcli) owns registration, SMS, data, call
  listing, dial-out, DTMF, and hangup — every one of those was
  exercised live on the owner's SIM7600G-H and read back.
- Voice *answering* goes through a direct libqmi client
  (QmiVoice below). ModemManager's own answer request is
  rejected by this unit's firmware (QMI error 41 InvalidQosId,
  the call terminating in the same instant), while a direct
  `answer_call` connects. There is deliberately no accept()
  on the ModemManager side of this module: an API that cannot
  silently fall back to the broken path cannot regress into it.

mmcli is a subprocess binding on purpose for v1: it is the
exact surface the live session proved, it needs no new
dependencies, and every call flows through one injectable
runner, so a D-Bus-native client can replace it later without
any caller changing.

Sleep behavior (docs/POWER-AND-WAKE.md): every binding here
dies with the host's sleep. On wake the worker constructs a
fresh LinuxModem (device open and client allocation happen in
QmiVoice.answer_ringing each time it is called, so a stale
client is never reused), and reconcile reads back whatever the
modem held through the sleep — SMS is store-and-forward, and
missed calls surface as records, never as silent gaps.
"""
import re
import subprocess
import time

from .modem import ModemError

SMS_PATH_RE = re.compile(r"/org/freedesktop/ModemManager1/SMS/\d+")
CALL_PATH_RE = re.compile(r"/org/freedesktop/ModemManager1/Call/\d+")


def subprocess_runner(args):
    """Run a command, return (returncode, stdout, stderr)."""
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def parse_keyvalue(text):
    """mmcli --output-keyvalue: 'key : value' lines -> dict."""
    out = {}
    for line in text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


class MmClient:
    """ModemManager duties, all through the injectable runner."""

    def __init__(self, runner=subprocess_runner):
        self.run = runner

    def _mmcli(self, *args):
        rc, out, err = self.run(["mmcli", *args])
        return out + err

    def probe(self):
        """Identity + readiness, read-only."""
        kv = parse_keyvalue(self._mmcli("-m", "any",
                                        "--output-keyvalue"))
        if "modem.generic.equipment-identifier" not in kv:
            raise ModemError("no modem reported by ModemManager")
        return {
            "model": kv.get("modem.generic.model"),
            "imei": kv.get("modem.generic.equipment-identifier"),
            "state": kv.get("modem.generic.state"),
            "signal": kv.get("modem.generic.signal-quality.value"),
            "operator": kv.get("modem.3gpp.operator-name"),
        }

    # -- calls ------------------------------------------------

    def list_calls(self):
        out = self._mmcli("-m", "any", "--voice-list-calls")
        return CALL_PATH_RE.findall(out)

    def call_info(self, path):
        return parse_keyvalue(self._mmcli("--call=" + path,
                                          "--output-keyvalue"))

    def call_state(self, path):
        return self.call_info(path).get("call.properties.state")

    def wait_for_ringing(self, timeout=120.0, poll_s=0.3):
        """Poll the call list until a call is ringing in.
        Returns (path, number-or-None)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            for path in self.list_calls():
                info = self.call_info(path)
                if "ringing" in (info.get("call.properties.state")
                                 or ""):
                    return path, info.get("call.properties.number")
            time.sleep(poll_s)
        raise ModemError("no incoming call before timeout")

    def dial(self, number):
        """Place a call and start it. Returns the call path.
        Proven live (carrier voicemail retrieval test)."""
        out = self._mmcli("-m", "any",
                          f"--voice-create-call=number={number}")
        m = CALL_PATH_RE.search(out)
        if not m:
            raise ModemError(f"call creation failed: {out.strip()}")
        path = m.group(0)
        res = self._mmcli("--call=" + path, "--start")
        if "successfully" not in res:
            raise ModemError(f"call start failed: {res.strip()}")
        return path

    def send_dtmf(self, path, digits):
        res = self._mmcli("--call=" + path, f"--send-dtmf={digits}")
        if "successfully" not in res:
            raise ModemError(f"dtmf failed: {res.strip()}")

    def hangup(self, path):
        self._mmcli("--call=" + path, "--hangup")

    # -- SMS --------------------------------------------------

    def send_sms(self, number, text):
        """Create + send an SMS; returns the state read back
        after sending (the word of the modem, not the request)."""
        out = self._mmcli("-m", "any",
                          f"--messaging-create-sms=number={number},"
                          f"text={text}")
        m = SMS_PATH_RE.search(out)
        if not m:
            raise ModemError(f"sms creation failed: {out.strip()}")
        path = m.group(0)
        res = self._mmcli("--sms=" + path, "--send")
        if "successfully" not in res:
            raise ModemError(f"sms send failed: {res.strip()}")
        kv = parse_keyvalue(self._mmcli("--sms=" + path,
                                        "--output-keyvalue"))
        return kv.get("sms.properties.state")

    def list_sms(self):
        out = self._mmcli("-m", "any", "--messaging-list-sms")
        return SMS_PATH_RE.findall(out)

    def read_sms(self, path):
        kv = parse_keyvalue(self._mmcli("--sms=" + path,
                                        "--output-keyvalue"))
        return {
            "number": kv.get("sms.content.number"),
            "text": kv.get("sms.content.data"),
            "state": kv.get("sms.properties.state"),
        }


class FakeQmiVoice:
    """Scripted stand-in for tests: records answer attempts and
    returns the scripted outcome. A test double lives next to
    the real class so the facade's routing (answer goes to QMI,
    never to ModemManager) is itself under test."""

    def __init__(self, result=True):
        self.result = result
        self.answered = []

    def answer_ringing(self, timeout=30.0):
        self.answered.append(timeout)
        if not self.result:
            raise ModemError("qmi answer failed (scripted)")
        return True


class LibqmiVoice:
    """Direct libqmi answer path (PyGObject; imported lazily so
    this module loads on machines without the bindings).

    The flow mirrors the harness that answered the owner's call
    live: open the QMI device through the proxy (so the client
    coexists with ModemManager), allocate a VOICE client, read
    the call list, and issue answer_call for the ringing call.
    """

    def __init__(self, device_path="/dev/cdc-wdm0"):
        self.device_path = device_path

    def answer_ringing(self, timeout=30.0):
        import gi
        gi.require_version("Qmi", "1.0")
        from gi.repository import Gio, GLib, Qmi

        canc = Gio.Cancellable.new()
        loop = GLib.MainLoop()
        box = {"done": False, "ok": False, "err": None}

        def finish(ok, err=None):
            if not box["done"]:
                box.update(done=True, ok=ok, err=err)
                loop.quit()

        def on_answer(client, result):
            try:
                client.answer_call_finish(result)
                finish(True)
            except Exception as e:  # the firmware's word, verbatim
                finish(False, f"answer_call: {e}")

        def on_info(client, result):
            try:
                out = client.get_all_call_info_finish(result)
                infos = out.get_call_information()
            except Exception as e:
                finish(False, f"get_all_call_info: {e}")
                return
            call_id = self._ringing_call_id(infos)
            inp = Qmi.MessageVoiceAnswerCallInput.new()
            inp.set_call_id(call_id)
            try:
                client.answer_call(inp, 10, canc, on_answer)
            except TypeError:
                client.answer_call(inp, 10, canc, on_answer, None)

        def on_client(dev, result):
            try:
                client = dev.allocate_client_finish(result)
            except Exception as e:
                finish(False, f"allocate_client: {e}")
                return
            # input slot is a real parameter in this binding:
            # (input, timeout, cancellable, callback)
            client.get_all_call_info(None, 10, canc, on_info)

        def on_open(dev, result):
            try:
                dev.open_finish(result)
            except Exception as e:
                finish(False, f"device open: {e}")
                return
            dev.allocate_client(Qmi.Service.VOICE, Qmi.CID_NONE,
                                10, canc, on_client)

        def on_new(_src, result):
            try:
                dev = Qmi.Device.new_finish(result)
            except Exception as e:
                finish(False, f"device new: {e}")
                return
            dev.open(Qmi.DeviceOpenFlags.PROXY
                     | Qmi.DeviceOpenFlags.SYNC, 15, canc, on_open)

        Qmi.Device.new(Gio.File.new_for_path(self.device_path),
                       canc, on_new)
        GLib.timeout_add_seconds(int(timeout),
                                 lambda: finish(False, "timeout"))
        loop.run()
        if not box["ok"]:
            raise ModemError(f"qmi answer failed: {box['err']}")
        return True

    @staticmethod
    def _ringing_call_id(infos):
        """Best call-id extraction across binding shapes. During
        a ring on an otherwise idle modem the ringing call is the
        list's only entry; the explicit accessors are tried first
        and the single-entry case is the documented fallback —
        the same ladder the live harness climbed."""
        if not infos:
            raise ModemError("no calls reported by qmi")
        first = infos[0] if isinstance(infos, (list, tuple)) \
            else infos
        for name in ("call_id", "id"):
            v = getattr(first, name, None)
            if isinstance(v, int):
                return v
        for name in ("get_call_id", "get_id"):
            fn = getattr(first, name, None)
            if callable(fn):
                v = fn()
                if isinstance(v, int):
                    return v
        return 1


class LinuxModem:
    """The modem worker's Linux facade: one object, the verbs
    the call/SMS flows need, each routed to its proven binding."""

    def __init__(self, mm=None, voice=None):
        self.mm = mm or MmClient()
        self.voice = voice or LibqmiVoice()

    def probe(self):
        return self.mm.probe()

    def wait_for_call(self, timeout=120.0):
        """Returns (path, number) for the ringing call."""
        return self.mm.wait_for_ringing(timeout=timeout)

    def answer(self):
        """Answer the ringing call via direct QMI. There is no
        ModemManager fallback by design (see module docstring)."""
        return self.voice.answer_ringing()

    def hangup(self, path):
        self.mm.hangup(path)

    def dial(self, number):
        return self.mm.dial(number)

    def send_dtmf(self, path, digits):
        self.mm.send_dtmf(path, digits)

    def send_sms(self, number, text):
        return self.mm.send_sms(number, text)

    def read_sms(self, path):
        return self.mm.read_sms(path)


if __name__ == "__main__":
    import sys
    if "--probe" in sys.argv:
        print(LinuxModem().probe())
    else:
        print("usage: python -m staxline.qmi_modem --probe")
