import threading
import time
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_cache_state():
    import app.cache as c

    original_redis = c._redis_client
    original_attempted = c._redis_initAttempted
    original_fail = c._redis_lastFail
    original_memory = dict(c._memory)
    c._redis_client = None
    c._redis_initAttempted = False
    c._redis_lastFail = 0.0
    c._memory.clear()
    yield
    c._redis_client = original_redis
    c._redis_initAttempted = original_attempted
    c._redis_lastFail = original_fail
    c._memory.clear()
    c._memory.update(original_memory)


# ---------------------------------------------------------------------------
# In-memory fallback
# ---------------------------------------------------------------------------

def test_put_and_get_in_memory():
    from app import cache

    cache.put("mem:key", {"a": 1}, ttl=60)
    assert cache.get("mem:key") == {"a": 1}


def test_get_returns_none_for_missing_key():
    from app import cache

    assert cache.get("no:such:key") is None


def test_ttl_expiry_in_memory():
    from app import cache

    cache.put("ttl:key", "value", ttl=0)
    time.sleep(0.05)
    assert cache.get("ttl:key") is None


def test_invalidate_by_prefix():
    from app import cache

    cache.put("pref:a", 1)
    cache.put("pref:b", 2)
    cache.put("other:c", 3)
    cache.invalidate("pref:")
    assert cache.get("pref:a") is None
    assert cache.get("pref:b") is None
    assert cache.get("other:c") == 3


def test_invalidate_all():
    from app import cache

    cache.put("x:1", 1)
    cache.put("y:2", 2)
    cache.invalidate()
    assert cache.get("x:1") is None
    assert cache.get("y:2") is None


def test_close_resets_redis_reference():
    from app import cache

    mock_redis = MagicMock()
    cache._redis_client = mock_redis
    cache.close()
    mock_redis.close.assert_called_once()
    assert cache._redis_client is None


def test_close_when_no_redis():
    from app import cache

    cache._redis_client = None
    cache.close()
    assert cache._redis_client is None


# ---------------------------------------------------------------------------
# Memory pruning
# ---------------------------------------------------------------------------

def test_memory_pruning_removes_oldest_entries():
    from app import cache

    for i in range(cache._MAX_MEMORY_ENTRIES + 60):
        cache.put(f"prune:{i}", i, ttl=3600)
    assert len(cache._memory) <= cache._MAX_MEMORY_ENTRIES + 50


def test_expired_entries_are_pruned():
    from app import cache

    cache.put("old:1", "a", ttl=0)
    cache.put("old:2", "b", ttl=0)
    cache.put("new:1", "c", ttl=3600)
    time.sleep(0.05)
    cache.put("trigger:prune", "x", ttl=3600)
    assert cache.get("old:1") is None
    assert cache.get("old:2") is None
    assert cache.get("new:1") == "c"


# ---------------------------------------------------------------------------
# Redis path (mocked)
# ---------------------------------------------------------------------------

def _make_mock_redis():
    store = {}

    def _get(key):
        return store.get(key)

    def _setex(key, ttl, value):
        store[key] = value

    def _delete(*keys):
        for k in keys:
            store.pop(k, None)

    def _scan(cursor, match, count):
        prefix = match.rstrip("*")
        matched = [k for k in store if k.startswith(prefix)]
        return 0, matched

    mock = MagicMock()
    mock.ping = MagicMock()
    mock.get = MagicMock(side_effect=_get)
    mock.setex = MagicMock(side_effect=_setex)
    mock.delete = MagicMock(side_effect=_delete)
    mock.scan = MagicMock(side_effect=_scan)
    mock.close = MagicMock()
    return mock, store


def test_redis_put_and_get():
    from app import cache

    mock, store = _make_mock_redis()
    cache._redis_client = mock
    cache._redis_initAttempted = True

    cache.put("redis:key", {"data": 42}, ttl=60)
    mock.setex.assert_called_once()
    result = cache.get("redis:key")
    assert result == {"data": 42}


def test_redis_get_miss_returns_none():
    from app import cache

    mock, store = _make_mock_redis()
    cache._redis_client = mock
    cache._redis_initAttempted = True

    assert cache.get("redis:miss") is None


def test_redis_invalidate_by_prefix():
    from app import cache

    mock, store = _make_mock_redis()
    cache._redis_client = mock
    cache._redis_initAttempted = True

    store["inv:a"] = b"data"
    store["inv:b"] = b"data"
    store["keep:c"] = b"data"
    cache.invalidate("inv:")
    assert "inv:a" not in store
    assert "inv:b" not in store
    assert "keep:c" in store


def test_redis_fallback_to_memory_on_failure():
    from app import cache

    mock = MagicMock()
    mock.ping = MagicMock()
    mock.get = MagicMock(side_effect=ConnectionError("down"))
    mock.setex = MagicMock(side_effect=ConnectionError("down"))
    cache._redis_client = mock
    cache._redis_initAttempted = True

    cache.put("fallback:key", "in_mem")
    assert cache.get("fallback:key") == "in_mem"


# ---------------------------------------------------------------------------
# Redis retry cooldown
# ---------------------------------------------------------------------------

def test_redis_retry_cooldown_prevents_immediate_retry():
    from app import cache

    cache._redis_initAttempted = True
    cache._redis_lastFail = time.monotonic()
    result = cache._get_redis()
    assert result is None


def test_redis_retry_after_cooldown():
    from app import cache

    cache._redis_initAttempted = True
    cache._redis_lastFail = time.monotonic() - cache._REDIS_RETRY_COOLDOWN - 1
    with patch.dict("os.environ", {"REDIS_URL": ""}):
        result = cache._get_redis()
    assert result is None
    assert cache._redis_initAttempted is True


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

def test_concurrent_put_get():
    from app import cache

    errors = []

    def writer(n):
        try:
            for i in range(50):
                cache.put(f"thread:{n}:{i}", i, ttl=60)
        except Exception as e:
            errors.append(e)

    def reader(n):
        try:
            for i in range(50):
                cache.get(f"thread:{n}:{i}")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
    threads += [threading.Thread(target=reader, args=(t,)) for t in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_pickle_roundtrip_for_pdf_bytes():
    from app import cache

    fake_pdf = b"%PDF-1.4 fake content " * 1000
    cache.put("pdf:test", fake_pdf, ttl=60)
    result = cache.get("pdf:test")
    assert result == fake_pdf


def test_pickle_roundtrip_for_complex_dict():
    from app import cache

    data = {
        "courses": [{"id": i, "title": f"Course {i}", "units": [{"title": f"Unit {j}", "content": "x"} for j in range(4)]} for i in range(10)]
    }
    cache.put("complex:test", data, ttl=60)
    assert cache.get("complex:test") == data
