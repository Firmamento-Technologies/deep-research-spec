# DRS Integration Tests

## Overview

Comprehensive integration tests for the Deep Research System pipeline.

## Test Files

- **`test_api_endpoints.py`**: REST API endpoint tests
- **`test_sse_streaming.py`**: SSE streaming and event delivery tests
- **`test_cancel_run.py`**: Run cancellation tests
- **`test_full_pipeline.py`**: End-to-end pipeline execution tests

## Running Tests

### All tests
```bash
cd backend
pytest tests/ -v
```

### Specific test file
```bash
pytest tests/test_api_endpoints.py -v
```

### Exclude slow tests
```bash
pytest tests/ -m "not slow"
```

### With coverage
```bash
pytest tests/ --cov=src --cov-report=html
```

## Test Fixtures

### `async_client`
FastAPI TestClient with async support for API requests.

### `test_db`
In-memory SQLite database for isolated tests.

### `mock_broker`
Mocked SSEBroker for testing event emission without Redis.

### `mock_llm_response`
Mocked LLM API response for testing without actual API calls.

### `wait_for_status`
Utility to poll run status until target status is reached.

## Test Requirements

```bash
pip install pytest pytest-asyncio httpx pytest-mock pytest-cov
```

## CI/CD Integration

Tests are designed to run in CI environments:
- No external dependencies (Redis, PostgreSQL, LLM APIs)
- Fast execution (< 30s for full suite, excluding slow tests)
- Clear failure messages
- Isolated (no shared state between tests)

## Writing New Tests

1. Create file `test_<feature>.py` in `tests/`
2. Use `@pytest.mark.asyncio` for async tests
3. Import fixtures from `conftest.py`
4. Add descriptive docstrings
5. Use markers for categorization:
   - `@pytest.mark.slow` for tests > 5s
   - `@pytest.mark.integration` for integration tests
   - `@pytest.mark.unit` for unit tests

## Example

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_my_feature(async_client: AsyncClient):
    """Test description."""
    response = await async_client.post(
        "/api/runs",
        json={"topic": "Test"},
    )
    
    assert response.status_code == 201
    data = response.json()
    assert "doc_id" in data
```
