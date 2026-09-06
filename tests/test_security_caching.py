import pytest
from unittest.mock import patch, MagicMock
from litellm_adk.security import PIIScrubber
from litellm_adk.caching import CacheManager
import litellm

def test_pii_scrubber_text():
    raw_text = "My SSN is 123-45-6789 and my email is test@example.com."
    scrubbed = PIIScrubber.scrub_text(raw_text)
    assert "123-45-6789" not in scrubbed
    assert "[SSN_REDACTED]" in scrubbed
    assert "test@example.com" not in scrubbed
    assert "[EMAIL_REDACTED]" in scrubbed

def test_pii_scrubber_messages():
    messages = [
        {"role": "user", "content": "Here is my credit card: 1234-5678-9012-3456."}
    ]
    scrubbed = PIIScrubber.scrub_messages(messages)
    assert "1234-5678-9012-3456" not in scrubbed[0]["content"]
    assert "[CREDIT_CARD_REDACTED]" in scrubbed[0]["content"]
    # Ensure original is unmodified
    assert "1234-5678-9012-3456" in messages[0]["content"]

@patch("litellm.Cache")
def test_cache_manager_redis(mock_cache):
    CacheManager.enable_redis_cache(host="10.0.0.1", port=6380, semantic=False)
    mock_cache.assert_called_with(type="redis", host="10.0.0.1", port=6380, password=None, ttl=3600)
    assert litellm.cache is not None

@patch("litellm.Cache")
def test_cache_manager_dragonfly_semantic(mock_cache):
    CacheManager.enable_redis_cache(host="10.0.0.1", port=6380, semantic=True)
    mock_cache.assert_called_with(type="redis-semantic", host="10.0.0.1", port=6380, password=None, ttl=3600, similarity_threshold=0.8)
    
def test_cache_manager_disable():
    litellm.cache = MagicMock()
    CacheManager.disable_cache()
    assert litellm.cache is None
