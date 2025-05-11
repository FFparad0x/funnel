from collections import defaultdict
from typing import Dict

class RequestStats:
    def __init__(self):
        self.total_requests = 0
        self.channel_requests: Dict[str, int] = defaultdict(int)
        self.ask_requests: Dict[str, int] = defaultdict(int)

    def increment(self, channel_id: str, is_ask: bool = False):
        """Increment request counters."""
        self.total_requests += 1
        self.channel_requests[str(channel_id)] += 1
        if is_ask:
            self.ask_requests[str(channel_id)] += 1

    def get_stats(self) -> dict:
        """Get current statistics."""
        return {
            "total_requests": self.total_requests,
            "channel_requests": dict(self.channel_requests),
            "ask_requests": dict(self.ask_requests)
        }

# Create a global instance
request_stats = RequestStats() 