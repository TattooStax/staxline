"""The Linux modem binding, proven against a scripted runner.

No hardware is touched: every mmcli call is scripted, and the
voice answer is a FakeQmiVoice. What these tests pin down is
the routing the live session earned — above all that answering
a call never goes through ModemManager (firmware-rejected on
the real unit), and that an SMS 'sent' is the state read back
from the modem, not the state the caller hoped for.
"""
import unittest

from staxline.modem import ModemError
from staxline.qmi_modem import FakeQmiVoice, LinuxModem, MmClient

MODEM_KV = """modem.generic.equipment-identifier : 862636058646900
modem.generic.model                : SIMCOM_SIM7600G-H
modem.generic.state                : registered
modem.generic.signal-quality.value : 70
modem.3gpp.operator-name           : T-Mobile
"""

RINGING_LIST = "/org/freedesktop/ModemManager1/Call/1\n"
CALL_KV = """call.properties.state   : ringing-in
call.properties.number  : +17018317231
"""


class ScriptedRunner:
    """Answers mmcli invocations by substring match and records
    every argv it was given."""

    def __init__(self, table):
        self.table = table  # list of (substring, (rc, out, err))
        self.calls = []

    def __call__(self, args):
        self.calls.append(args)
        joined = " ".join(args)
        for needle, resp in self.table:
            if needle in joined:
                return resp
        return (1, "", "unscripted: " + joined)


def make_modem(runner, voice=None):
    return LinuxModem(mm=MmClient(runner=runner),
                      voice=voice or FakeQmiVoice())


class ProbeTests(unittest.TestCase):
    def test_probe_parses_keyvalue(self):
        r = ScriptedRunner([("--output-keyvalue", (0, MODEM_KV, ""))])
        info = make_modem(r).probe()
        self.assertEqual(info["imei"], "862636058646900")
        self.assertEqual(info["model"], "SIMCOM_SIM7600G-H")
        self.assertEqual(info["operator"], "T-Mobile")
        self.assertEqual(info["signal"], "70")

    def test_probe_without_modem_raises(self):
        r = ScriptedRunner([("--output-keyvalue",
                             (0, "modem.generic.state : failed\n",
                              ""))])
        with self.assertRaises(ModemError):
            make_modem(r).probe()


class CallRoutingTests(unittest.TestCase):
    def ringing_runner(self):
        return ScriptedRunner([
            ("--voice-list-calls", (0, RINGING_LIST, "")),
            ("--output-keyvalue", (0, CALL_KV, "")),
        ])

    def test_wait_for_call_returns_number(self):
        path, number = make_modem(self.ringing_runner()) \
            .wait_for_call(timeout=2)
        self.assertTrue(path.endswith("/Call/1"))
        self.assertEqual(number, "+17018317231")

    def test_answer_goes_to_qmi_never_to_mmcli_accept(self):
        r = self.ringing_runner()
        voice = FakeQmiVoice()
        modem = make_modem(r, voice=voice)
        modem.wait_for_call(timeout=2)
        self.assertTrue(modem.answer())
        self.assertEqual(len(voice.answered), 1)
        for argv in r.calls:
            self.assertNotIn("--accept", argv)

    def test_answer_failure_surfaces_as_modem_error(self):
        modem = make_modem(self.ringing_runner(),
                           voice=FakeQmiVoice(result=False))
        with self.assertRaises(ModemError):
            modem.answer()

    def test_dial_dtmf_hangup_shapes(self):
        r = ScriptedRunner([
            ("--voice-create-call",
             (0, "Successfully created new call: "
                 "/org/freedesktop/ModemManager1/Call/3", "")),
            ("--start", (0, "successfully started the call", "")),
            ("--send-dtmf", (0, "successfully send dtmf", "")),
            ("--hangup", (0, "successfully hung up", "")),
        ])
        modem = make_modem(r)
        path = modem.dial("+18056377243")
        self.assertTrue(path.endswith("/Call/3"))
        modem.send_dtmf(path, "1")
        modem.hangup(path)


class SmsTests(unittest.TestCase):
    def test_send_sms_returns_readback_state(self):
        r = ScriptedRunner([
            ("--messaging-create-sms",
             (0, "Successfully created new SMS: "
                 "/org/freedesktop/ModemManager1/SMS/14", "")),
            ("--send", (0, "successfully sent the message", "")),
            ("--output-keyvalue",
             (0, "sms.properties.state : sent\n", "")),
        ])
        state = make_modem(r).send_sms("+17018317231", "hi")
        self.assertEqual(state, "sent")

    def test_read_sms_parses_content(self):
        kv = ("sms.content.number : +17018317231\n"
              "sms.content.data   : What services do you offer\n"
              "sms.properties.state : received\n")
        r = ScriptedRunner([("--output-keyvalue", (0, kv, ""))])
        msg = make_modem(r).read_sms(
            "/org/freedesktop/ModemManager1/SMS/15")
        self.assertEqual(msg["text"], "What services do you offer")
        self.assertEqual(msg["state"], "received")


if __name__ == "__main__":
    unittest.main()
