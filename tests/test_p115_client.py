import threading
import time
import unittest
from unittest.mock import patch

from modules.p115_client import P115ClientWrapper


class _FakeClient:
    created = 0
    active = 0
    max_active = 0
    guard = threading.Lock()

    def __init__(self, _cookies):
        type(self).created += 1
        self.number = type(self).created

    def upload_init(self, _payload):
        with type(self).guard:
            type(self).active += 1
            type(self).max_active = max(type(self).max_active, type(self).active)
        try:
            time.sleep(0.01)
            if self.number == 1:
                raise IndexError("index out of bounds on dimension 1")
            return {"status": 2, "pickcode": "ok"}
        finally:
            with type(self).guard:
                type(self).active -= 1


class P115ClientWrapperTests(unittest.TestCase):
    def setUp(self):
        _FakeClient.created = 0
        _FakeClient.active = 0
        _FakeClient.max_active = 0

    @patch("modules.p115_client.P115Client", _FakeClient)
    def test_rebuilds_client_after_corrupt_upload_state(self):
        client = P115ClientWrapper({"retry_times": 2, "retry_delay": 0})

        result = client.check_rapid_upload("a.mkv", 123, "ABC")

        self.assertTrue(result["success"])
        self.assertTrue(result["can_rapid"])
        self.assertEqual(_FakeClient.created, 2)

    @patch("modules.p115_client.P115Client", _FakeClient)
    def test_serializes_upload_init_across_threads(self):
        # Skip the deliberate first-instance failure used by the recovery test.
        _FakeClient.created = 1
        client = P115ClientWrapper({"retry_times": 1, "retry_delay": 0})
        threads = [
            threading.Thread(
                target=client.check_rapid_upload,
                args=(f"{index}.mkv", 123, "ABC"),
            )
            for index in range(2)
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(_FakeClient.max_active, 1)


if __name__ == "__main__":
    unittest.main()
