import unittest
import io
import json
import struct
from idm_native_host.host import read_native_message, send_native_message, handle_browser_message


class TestNativeHost(unittest.TestCase):
    def test_native_messaging_framing(self):
        test_payload = {"action": "ping", "test": True}
        json_bytes = json.dumps(test_payload).encode("utf-8")
        raw_input = struct.pack("<I", len(json_bytes)) + json_bytes

        stream_in = io.BytesIO(raw_input)
        decoded = read_native_message(stream_in)
        self.assertEqual(decoded, test_payload)

        stream_out = io.BytesIO()
        send_native_message(test_payload, stream_out)
        stream_out.seek(0)
        out_header = stream_out.read(4)
        out_len = struct.unpack("<I", out_header)[0]
        out_payload = json.loads(stream_out.read(out_len).decode("utf-8"))
        self.assertEqual(out_payload, test_payload)

    def test_handle_browser_message_ping(self):
        res = handle_browser_message({"action": "ping"}, ipc_client=None)
        self.assertTrue(res.get("pong", False))


if __name__ == "__main__":
    unittest.main()
