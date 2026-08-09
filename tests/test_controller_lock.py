import threading
import time
import unittest

from modules.controller import _serialized_processing


class _Worker:
    def __init__(self):
        self._processing_lock = threading.RLock()
        self.active = 0
        self.max_active = 0
        self.guard = threading.Lock()

    @_serialized_processing
    def run(self):
        with self.guard:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(0.01)
        finally:
            with self.guard:
                self.active -= 1


class ControllerProcessingLockTests(unittest.TestCase):
    def test_serializes_complete_processing_runs(self):
        worker = _Worker()
        threads = [threading.Thread(target=worker.run) for _ in range(3)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(worker.max_active, 1)


if __name__ == "__main__":
    unittest.main()
