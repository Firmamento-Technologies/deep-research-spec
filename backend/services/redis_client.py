# Shared Redis async client — created once at import time.
# The client is lazy-connected: the actual TCP connection is established
# on the first command, not at import.

import redis.asyncio as aioredis
from config.settings import settings

redis: aioredis.Redis = aioredis.from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,
)
