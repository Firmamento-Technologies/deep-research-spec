"""Pytest fixtures for integration tests."""

import asyncio
import pytest
from typing import AsyncGenerator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from database.models import Base
from database.connection import get_db
from api.dependencies import require_user
from api.runs import router as runs_router
from fastapi import FastAPI

# ---------------------------------------------------------------------------
# Test Database
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create in-memory SQLite database for tests."""
    # Create in-memory engine
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
    
    # Cleanup
    await engine.dispose()


# ---------------------------------------------------------------------------
# Test Client
# ---------------------------------------------------------------------------

@pytest.fixture
async def async_client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create FastAPI test client with test database."""
    # Create test app
    app = FastAPI()
    app.include_router(runs_router)
    
    # Override DB dependency
    async def override_get_db():
        yield test_db

    async def override_require_user():
        return {"id": "test-user", "role": "user"}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_user] = override_require_user
    
    # Create async client
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def unauthenticated_client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create FastAPI test client without auth override."""
    app = FastAPI()
    app.include_router(runs_router)

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Mock Services
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    return {
        "content": "Test response content",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
        "cost_usd": 0.001,
    }


@pytest.fixture
def mock_broker():
    """Mock SSEBroker for testing."""
    class MockBroker:
        def __init__(self):
            self.events = []
        
        async def emit(self, doc_id: str, event_type: str, payload: dict):
            self.events.append({
                "doc_id": doc_id,
                "type": event_type,
                "payload": payload,
            })
        
        async def subscribe(self, doc_id: str):
            for event in self.events:
                if event["doc_id"] == doc_id:
                    yield event
    
    return MockBroker()


# ---------------------------------------------------------------------------
# Test Utilities
# ---------------------------------------------------------------------------

@pytest.fixture
def wait_for_status():
    """Utility to poll run status until condition met."""
    async def _wait(
        client: AsyncClient,
        doc_id: str,
        target_status: str,
        timeout: float = 30.0,
        interval: float = 0.5,
    ) -> dict:
        """Poll GET /api/runs/{doc_id} until status matches."""
        elapsed = 0.0
        while elapsed < timeout:
            response = await client.get(f"/api/runs/{doc_id}")
            if response.status_code == 200:
                data = response.json()
                if data["status"] == target_status:
                    return data
            
            await asyncio.sleep(interval)
            elapsed += interval
        
        raise TimeoutError(
            f"Status did not reach '{target_status}' within {timeout}s"
        )
    
    return _wait
