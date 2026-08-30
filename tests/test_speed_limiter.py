import unittest
import time
from idm_core.speed_limiter import SpeedLimiter


class TestSpeedLimiter(unittest.TestCase):
    def test_unlimited_rate(self):
        limiter = SpeedLimiter(rate_limit_bps=0)
        start = time.time()
        limiter.acquire(1024 * 1024)
        elapsed = time.time() - start
        self.assertLess(elapsed, 0.05)

    def test_throttling(self):
        # 100 KB/sec limit
        limiter = SpeedLimiter(rate_limit_bps=100 * 1024)
        start = time.time()
        # Acquire 50 KB twice
        limiter.acquire(50 * 1024)
        limiter.acquire(50 * 1024)
        elapsed = time.time() - start
        # 100 KB at 100 KB/s should take around 0.5 - 1.0s depending on initial burst
        self.assertGreaterEqual(elapsed, 0.2)

    def test_dynamic_rate_adjustment(self):
        limiter = SpeedLimiter(rate_limit_bps=1000)
        self.assertEqual(limiter.rate_limit_bps, 1000)
        limiter.set_rate_limit(5000)
        self.assertEqual(limiter.rate_limit_bps, 5000)


if __name__ == "__main__":
    unittest.main()
