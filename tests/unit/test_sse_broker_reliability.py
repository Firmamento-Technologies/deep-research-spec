import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("redis")

backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

spec = importlib.util.spec_from_file_location("backend_services_sse_broker", backend_path / "services" / "sse_broker.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SSEBroker = module.SSEBroker


class FakePubSub:
    def __init__(self, messages):
        self._messages = messages

    async def subscribe(self, _channel):
        return None

    async def listen(self):
        for msg in self._messages:
            yield msg

    async def unsubscribe(self, _channel):
        return None

    async def close(self):
        return None


class FakeRedis:
    def __init__(self, messages=None):
        self.storage = {}
        self.messages = messages or []

    async def publish(self, _channel, _payload):
        return 1

    def pubsub(self):
        return FakePubSub(self.messages)

    async def get(self, key):
        return self.storage.get(key)

    async def set(self, key, value, ex=None):
        self.storage[key] = value

    async def delete(self, key):
        self.storage.pop(key, None)


@pytest.mark.asyncio
async def test_heartbeat_emitted_when_timer_completes():
    redis = FakeRedis(messages=[{"type": "message", "data": '{"type":"X","payload":{},"doc_id":"d"}'}])
    broker = SSEBroker(redis)

    async def immediate_heartbeat():
        return {"type": "HEARTBEAT", "payload": {}, "timestamp": "t"}

    broker._heartbeat = immediate_heartbeat  # type: ignore[attr-defined]

    out = []
    async for event in broker.subscribe("d"):
        out.append(event)

    assert any(e.get("type") == "HEARTBEAT" for e in out)
    assert any(e.get("type") == "X" for e in out)


@pytest.mark.asyncio
async def test_outline_approval_persisted_without_waiter():
    redis = FakeRedis()
    broker = SSEBroker(redis)

    await broker.submit_outline_approval("doc-1", {"approved": True, "sections": [{"title": "A"}]})
    sections = await broker.wait_for_outline_approval("doc-1", default_sections=[])

    assert sections == [{"title": "A"}]


@pytest.mark.asyncio
async def test_section_approval_persisted_without_waiter():
    redis = FakeRedis()
    broker = SSEBroker(redis)

    await broker.submit_section_approval("doc-1", 2, {"approved": True, "content": "edited"})
    content = await broker.wait_for_section_approval("doc-1", 2, default_content="default")

    assert content == "edited"


@pytest.mark.asyncio
async def test_cross_worker_persisted_approval_visible_to_other_broker_instance():
    shared = FakeRedis()
    broker_a = SSEBroker(shared)
    broker_b = SSEBroker(shared)

    await broker_a.submit_outline_approval("doc-cross", {"approved": True, "sections": [{"title": "X"}]})
    sections = await broker_b.wait_for_outline_approval("doc-cross", default_sections=[])

    assert sections == [{"title": "X"}]
