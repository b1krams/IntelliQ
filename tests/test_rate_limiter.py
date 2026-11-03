"""Unit tests for atomic DynamoDB rate limiter and tumbling window quota enforcement."""
import pytest
from core.db import RateLimitExceeded, check_and_increment_rate_limit


def test_rate_limiter_within_quota():
    """Verify that requests within quota increment successfully."""
    client_id = "test-client-allowed"
    # Execute 5 requests with limit of 10
    for i in range(1, 6):
        count = check_and_increment_rate_limit(client_id, max_requests=10, window_seconds=60)
        assert count == i


def test_rate_limiter_exceeds_quota():
    """Verify that request exceeding quota raises RateLimitExceeded with positive Retry-After."""
    client_id = "test-client-throttled"
    limit = 3

    # Consume quota
    for _ in range(limit):
        check_and_increment_rate_limit(client_id, max_requests=limit, window_seconds=60)

    # The 4th request must fail with RateLimitExceeded
    with pytest.raises(RateLimitExceeded) as exc_info:
        check_and_increment_rate_limit(client_id, max_requests=limit, window_seconds=60)

    assert exc_info.value.retry_after_seconds > 0
    assert exc_info.value.retry_after_seconds <= 60

