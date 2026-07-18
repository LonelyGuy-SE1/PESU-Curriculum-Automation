import logging
import os
import pickle
import time
import threading

logger = logging.getLogger(__name__)

DEFAULT_TTL = 60
_MAX_MEMORY_ENTRIES = 500
_REDIS_RETRY_COOLDOWN = 60

_redis_client = None
_redis_initAttempted = False
_redis_lastFail = 0.0
_lock = threading.Lock()
_memory: dict[str, tuple[float, int, object]] = {}


def _get_redis():
    global _redis_client, _redis_initAttempted, _redis_lastFail
    if _redis_client is not None:
        return _redis_client
    if _redis_initAttempted:
        if time.monotonic() - _redis_lastFail < _REDIS_RETRY_COOLDOWN:
            return None
        _redis_initAttempted = False
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        _redis_initAttempted = True
        return None
    try:
        import redis as _redis
        pool = _redis.ConnectionPool.from_url(
            url,
            decode_responses=False,
            max_connections=10,
            socket_connect_timeout=5,
            socket_timeout=10,
        )
        client = _redis.Redis(connection_pool=pool)
        client.ping()
        _redis_client = client
        _redis_initAttempted = True
        logger.info("Redis connected to %s", url.split("@")[-1] if "@" in url else url)
        return _redis_client
    except Exception:
        logger.exception("Redis connection failed, falling back to in-memory cache")
        _redis_client = None
        _redis_initAttempted = True
        _redis_lastFail = time.monotonic()
        return None


def _prune_memory():
    now = time.monotonic()
    expired = [k for k, (ts, ttl, _) in _memory.items() if now - ts > ttl]
    for k in expired:
        del _memory[k]
    if len(_memory) > _MAX_MEMORY_ENTRIES:
        oldest = sorted(_memory, key=lambda k: _memory[k][0])[:len(_memory) - _MAX_MEMORY_ENTRIES]
        for k in oldest:
            del _memory[k]


def get(key: str) -> object | None:
    r = _get_redis()
    if r is not None:
        try:
            raw = r.get(key)
            if raw is None:
                return None
            return pickle.loads(raw)
        except Exception:
            logger.debug("Redis GET failed for key=%s", key)
    with _lock:
        entry = _memory.get(key)
        if entry is None:
            return None
        ts, ttl, value = entry
        if time.monotonic() - ts > ttl:
            del _memory[key]
            return None
        return value


def put(key: str, value: object, ttl: int = DEFAULT_TTL) -> None:
    r = _get_redis()
    if r is not None:
        try:
            r.setex(key, ttl, pickle.dumps(value))
            return
        except Exception:
            logger.debug("Redis SET failed for key=%s", key)
    with _lock:
        _memory[key] = (time.monotonic(), ttl, value)
        if len(_memory) > _MAX_MEMORY_ENTRIES + 50:
            _prune_memory()


def invalidate(prefix: str = "") -> None:
    r = _get_redis()
    if r is not None:
        try:
            if not prefix:
                r.flushdb()
                return
            cursor = 0
            while True:
                cursor, keys = r.scan(cursor, match=f"{prefix}*", count=100)
                if keys:
                    r.delete(*keys)
                if cursor == 0:
                    break
            return
        except Exception:
            logger.debug("Redis INVALIDATE failed for prefix=%s", prefix)
    with _lock:
        if not prefix:
            _memory.clear()
            return
        keys = [k for k in _memory if k.startswith(prefix)]
        for k in keys:
            del _memory[k]


def close() -> None:
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.close()
        except Exception:
            pass
        _redis_client = None
