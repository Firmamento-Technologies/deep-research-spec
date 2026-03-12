import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("redis")

backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

spec = importlib.util.spec_from_file_location(
    "backend_services_sse_broker",
    backend_path / "services" / "sse_broker.py",
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SSEBroker = module.SSEBroker


class FakePubSub:
    async def subscribe(self, _channel):
        return None

    async def listen(self):
        if False:
            yield None

    async def unsubscribe(self, _channel):
        return None

    async def close(self):
        return None


class FakeRedis:
    def __init__(self):
        self.storage = {}

    async def publish(self, _channel, _payload):
        return 1

    def pubsub(self):
        return FakePubSub()

    async def get(self, key):
        return self.storage.get(key)

    async def set(self, key, value, ex=None):
        self.storage[key] = value

    async def delete(self, key):
        self.storage.pop(key, None)


@pytest.mark.asyncio
async def test_outline_approval_roundtrip_waiter_then_submit():
    redis = FakeRedis()
    broker = SSEBroker(redis)

    async def waiter():
        return await broker.wait_for_outline_approval("doc-rt", default_sections=[{"title": "default"}], timeout_s=1.0)

    task = asyncio.create_task(waiter())
    await asyncio.sleep(0)
    await broker.submit_outline_approval("doc-rt", {"approved": True, "sections": [{"title": "edited"}]})

    result = await task
    assert result == [{"title": "edited"}]


@pytest.mark.asyncio
async def test_section_approval_roundtrip_waiter_then_submit():
    redis = FakeRedis()
    broker = SSEBroker(redis)

    async def waiter():
        return await broker.wait_for_section_approval("doc-rt", 1, default_content="default", timeout_s=1.0)

    task = asyncio.create_task(waiter())
    await asyncio.sleep(0)
    await broker.submit_section_approval("doc-rt", 1, {"approved": True, "content": "edited"})

    result = await task
    assert result == "edited"
