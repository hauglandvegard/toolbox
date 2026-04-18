import logging
import random
import time
from collections import deque


class RateLimiter:
    """Handles 'flat', 'random' (jitter), and 'window' (X req/Y sec) rate limiting."""

    logger = logging.getLogger(__name__)

    def __init__(
        self,
        mode="flat",
        flat_delay=2.0,
        min_delay=1.0,
        max_delay=3.0,
        window_requests=10,
        window_seconds=60.0,
    ):
        """
        Initializes strategy: flat_delay (s), random range (min/max), or window (reqs/s).

        Args:
        - mode (str):Options: "flat", "random", "window".
                Defaults to "flat".
        """
        self.mode = mode

        # Flat configs
        self.flat_delay = flat_delay

        # Random configs
        self.min_delay = min_delay
        self.max_delay = max_delay

        # Window configs
        self.window_requests = window_requests
        self.window_seconds = window_seconds

        # State trackers
        self.last_request_time = 0.0
        self.request_timestamps = deque()

    def enforce(self):
        """Calculates and applies sleep time before a request; call before every network fetch."""
        current_time = time.time()

        if self.mode == "flat":
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.flat_delay:
                time_delta = self.flat_delay - time_since_last
                self.logger.debug(f"Flat limit: sleeping for {time_delta:.2f}s")
                time.sleep(time_delta)
            self.last_request_time = time.time()

        elif self.mode == "random":
            time_since_last = current_time - self.last_request_time
            random_delay = random.uniform(self.min_delay, self.max_delay)

            if time_since_last < random_delay:
                sleep_time = random_delay - time_since_last
                self.logger.debug(f"Random limit: sleeping for {sleep_time:.2f}s.")
                time.sleep(sleep_time)

            self.last_request_time = time.time()

        elif self.mode == "window":
            while self.request_timestamps and (
                current_time - self.request_timestamps[0] > self.window_seconds
            ):
                self.request_timestamps.popleft()

            if len(self.request_timestamps) >= self.window_requests:
                oldest_request = self.request_timestamps[0]
                sleep_time = self.window_seconds - (current_time - oldest_request)
                if sleep_time > 0:
                    self.logger.debug(
                        f"Window limit reached. Sleeping {sleep_time:.2f}s."
                    )
                    time.sleep(sleep_time)

            self.request_timestamps.append(time.time())
