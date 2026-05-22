"""
Redis broker configuration for Dramatiq.

This module is imported by both the FastAPI app (to send tasks)
and the Dramatiq worker process (to receive and execute tasks).
"""

from __future__ import annotations

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import AgeLimit, Retries, ShutdownNotifications, TimeLimit

from app.config import settings

# ── Broker Setup ──────────────────────────────────────────────────────────────

redis_broker = RedisBroker(
    url=settings.redis_url,
    middleware=[
        AgeLimit(),
        TimeLimit(),
        ShutdownNotifications(),
        Retries(max_retries=settings.DRAMATIQ_MAX_RETRIES),
    ],
)

dramatiq.set_broker(redis_broker)
