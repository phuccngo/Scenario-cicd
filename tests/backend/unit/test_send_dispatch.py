import importlib, sys, types
from unittest.mock import Mock
import pytest

@pytest.fixture
def dispatch_module(monkeypatch):
    # Mock database module
    db = types.ModuleType("db")
    db.SessionLocal = Mock()
    db.EventLog = type("EventLog", (), {
        "id": object(),
        "event_id": object()
    })
    db.release_tx = Mock()
    monkeypatch.setitem(sys.modules, "db", db)

    # Mock Redis
    redis = types.ModuleType("redis")
    redis.Redis = type("Redis", (), {
        "from_url": staticmethod(lambda *a, **k: Mock())
    })
    monkeypatch.setitem(sys.modules, "redis", redis)

    # Mock scheduler vì dispatch_scheduler import module này
    # ngay cả khi thực hiện đường xử lý Celery.
    scheduler = types.ModuleType("scheduler")
    scheduler.run_scheduler = Mock(return_value={"success": True})
    monkeypatch.setitem(sys.modules, "scheduler", scheduler)

    sys.modules.pop("send_dispatch", None)
    module = importlib.import_module("send_dispatch")

    yield module

    sys.modules.pop("send_dispatch", None)

def test_partition_key_priority(dispatch_module):
    assert dispatch_module.partition_key("B1", {"platform_user_id": "U"}, 7) == "b:B1"
    assert dispatch_module.partition_key(None, {"platform_user_id": "U"}, 7) == "u:7:U"
    assert dispatch_module.partition_key(None, {}, 7) == "h:7"

def test_send_queue_is_deterministic(dispatch_module):
    key = "b:BOOKING-1"
    assert dispatch_module.send_queue_for(key) == dispatch_module.send_queue_for(key)
    assert dispatch_module.send_queue_for(key).startswith("send_")

def test_event_context_tracks_queued_codes(dispatch_module):
    token = dispatch_module.begin_event("log", "source")
    try:
        dispatch_module._event_ctx.get()["queued"].append("CODE")
        assert dispatch_module.queued_codes() == ["CODE"]
    finally:
        dispatch_module.end_event(token)
    assert dispatch_module.queued_codes() == []

def test_claim_fails_open_when_redis_unavailable(dispatch_module, monkeypatch):
    monkeypatch.setattr(dispatch_module, "_get_redis",
                        lambda: (_ for _ in ()).throw(RuntimeError("redis down")))
    assert dispatch_module._claim("key") is True

def test_dispatch_inline_when_celery_disabled(dispatch_module, monkeypatch):
    scheduler = types.ModuleType("scheduler")
    scheduler.run_scheduler = Mock(return_value={"success": True})
    monkeypatch.setitem(sys.modules, "scheduler", scheduler)
    monkeypatch.setattr(dispatch_module, "_celery_enabled", lambda: False)
    result = dispatch_module.dispatch_scheduler(object(), 1, "WELCOME", "B1", {}, None)
    assert result == {"success": True}
    scheduler.run_scheduler.assert_called_once()

def test_inline_code_bypasses_celery(dispatch_module, monkeypatch):
    scheduler = types.ModuleType("scheduler")
    scheduler.run_scheduler = Mock(return_value={"success": True})
    monkeypatch.setitem(sys.modules, "scheduler", scheduler)
    monkeypatch.setattr(dispatch_module, "_celery_enabled", lambda: True)
    monkeypatch.setattr(dispatch_module, "INLINE_CODES", {"BKG_PROCESSING_NOTIFY"})
    result = dispatch_module.dispatch_scheduler(
        object(), 1, "BKG_PROCESSING_NOTIFY", "B1", {}, None)
    assert result == {"success": True}
    scheduler.run_scheduler.assert_called_once()

def install_task(monkeypatch, task):
    tasks = types.ModuleType("auto_scheduler.tasks")
    tasks.run_scheduler_task = task
    package = types.ModuleType("auto_scheduler")
    package.__path__ = []
    monkeypatch.setitem(sys.modules, "auto_scheduler", package)
    monkeypatch.setitem(sys.modules, "auto_scheduler.tasks", tasks)

def test_dispatch_enqueues_celery(dispatch_module, monkeypatch):
    dispatch_module.release_tx = Mock()
    monkeypatch.setattr(dispatch_module, "_celery_enabled", lambda: True)
    monkeypatch.setattr(dispatch_module, "_claim", lambda key: True)
    monkeypatch.setattr(dispatch_module, "_cancel_near_due_scheduled_jobs", lambda *a: 0)
    task = Mock()
    install_task(monkeypatch, task)
    token = dispatch_module.begin_event("log-id", "source-id")
    try:
        result = dispatch_module.dispatch_scheduler(
            object(), 3, "SALE_SPA", "BOOK-1", {"x": 1}, ["image"])
        assert result["success"] and result["queued"]
        task.apply_async.assert_called_once()
        assert dispatch_module.queued_codes() == ["SALE_SPA"]
    finally:
        dispatch_module.end_event(token)

def test_duplicate_event_is_not_enqueued(dispatch_module, monkeypatch):
    monkeypatch.setattr(dispatch_module, "_celery_enabled", lambda: True)
    monkeypatch.setattr(dispatch_module, "_claim", lambda key: False)
    task = Mock()
    install_task(monkeypatch, task)
    token = dispatch_module.begin_event("log", "source")
    try:
        result = dispatch_module.dispatch_scheduler(
            object(), 1, "SALE_SPA", "B1", {}, None)
        assert result["duplicate"] is True
        task.apply_async.assert_not_called()
    finally:
        dispatch_module.end_event(token)

def test_celery_failure_falls_back_to_inline(dispatch_module, monkeypatch):
    scheduler = types.ModuleType("scheduler")
    scheduler.run_scheduler = Mock(return_value={"inline": True})
    monkeypatch.setitem(sys.modules, "scheduler", scheduler)
    dispatch_module.release_tx = Mock()
    monkeypatch.setattr(dispatch_module, "_celery_enabled", lambda: True)
    monkeypatch.setattr(dispatch_module, "_claim", lambda key: True)
    monkeypatch.setattr(dispatch_module, "_unclaim", Mock())
    monkeypatch.setattr(dispatch_module, "_cancel_near_due_scheduled_jobs", lambda *a: 0)
    task = Mock()
    task.apply_async.side_effect = RuntimeError("broker down")
    install_task(monkeypatch, task)
    result = dispatch_module.dispatch_scheduler(
        object(), 1, "SALE_SPA", "B1", {}, None)
    assert result == {"inline": True}
    scheduler.run_scheduler.assert_called_once()
    dispatch_module._unclaim.assert_called_once()
