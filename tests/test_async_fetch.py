from unittest.mock import AsyncMock

import pytest

from app.session import AlexaSession


@pytest.mark.asyncio
async def test_evaluate_fetch_uses_async_fetch_and_polls_result():
    session = AlexaSession.__new__(AlexaSession)
    session.evaluate = AsyncMock(side_effect=["request-id", "null", '{"status":200,"body":"ok"}', ""])

    result = await session._evaluate_fetch("/nexus/v1/graphql", "POST", '{query: "query { ping }"}')

    assert result == '{"status":200,"body":"ok"}'
    start_script = session.evaluate.await_args_list[0].args[0]
    assert "fetch(" in start_script
    assert "credentials: 'include'" in start_script
    assert "xhr.open" not in start_script
