"""Unit tests for scenario_queue using a fake db module.

The production db.py is deliberately not imported: these tests isolate queue
logic from database initialization and use lightweight model/session doubles.
"""
import importlib
import sys
import types
from datetime import datetime
from unittest.mock import MagicMock

import pytest


class FakeColumn:
    def __eq__(self, other):
        return ("eq", other)

    def __ne__(self, other):
        return ("ne", other)


class FakeModel:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def queue_module(monkeypatch):
    fake_db = types.ModuleType("db")
    fake_db.MessageQueue = type(
        "MessageQueue",
        (FakeModel,),
        {
            name: FakeColumn()
            for name in (
                "template_id", "booking_ref", "hotel_id", "status", "id"
            )
        },
    )
    fake_db.ScenarioTemplate = type(
        "ScenarioTemplate",
        (FakeModel,),
        {"id": FakeColumn(), "code": FakeColumn()},
    )

    # scenario_queue imports these symbols from SQLAlchemy at module load time.
    # The CI job installs application requirements, so use the real SQLAlchemy
    # modules; only the application's db module is replaced.
    monkeypatch.setitem(sys.modules, "db", fake_db)
    sys.modules.pop("scenario_queue", None)
    module = importlib.import_module("scenario_queue")
    yield module
    sys.modules.pop("scenario_queue", None)


def test_enqueue_creates_pending_record_and_commits(queue_module):
    db = MagicMock()
    db.refresh.side_effect = lambda record: None
    send_time = datetime(2026, 1, 1, 10, 0)
    creative = {"text": "Hello"}
    msg = types.SimpleNamespace(
        template_id=42,
        send_time=send_time,
        creative=creative,
    )

    result = queue_module.enqueue(db, 7, "BOOKING-1", msg, "TEST")

    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(result)
    assert result.hotel_id == 7
    assert result.booking_ref == "BOOKING-1"
    assert result.template_id == 42
    assert result.scheduled_at == send_time
    assert result.creative == creative
    assert result.status == "PENDING"
    assert result.created_by == "TEST"


def test_enqueue_uses_default_created_by(queue_module):
    db = MagicMock()
    msg = types.SimpleNamespace(
        template_id=1,
        send_time=datetime(2026, 1, 1, 10, 0),
        creative={},
    )

    result = queue_module.enqueue(db, 1, "B-1", msg)

    assert result.created_by == "STATIC_RULE"


def test_dequeue_returns_sent_messages_and_deletes_unsent(queue_module):
    sent = [object(), object()]
    db = MagicMock()
    query_sent = MagicMock()
    query_sent.filter.return_value.all.return_value = sent
    query_unsent = MagicMock()
    query_unsent.filter.return_value.delete.return_value = 2
    db.query.side_effect = [query_sent, query_unsent]

    result = queue_module.dequeue(db, 3, "B-2")

    assert result == sent
    query_sent.filter.assert_called_once()
    query_unsent.filter.assert_called_once()
    query_unsent.filter.return_value.delete.assert_called_once()
    db.commit.assert_called_once()


def test_cancel_conflicting_messages_marks_only_incompatible_ones(queue_module):
    compatible = types.SimpleNamespace(
        id=1,
        status="PENDING",
        template=types.SimpleNamespace(stage=["INSTAY"]),
    )
    incompatible = types.SimpleNamespace(
        id=2,
        status="PENDING",
        template=types.SimpleNamespace(stage=["PREARRIVAL"]),
    )
    query = MagicMock()
    query.join.return_value = query
    query.filter.return_value = query
    query.all.return_value = [compatible, incompatible]
    db = MagicMock()
    db.query.return_value = query

    result = queue_module.cancel_conflicting_messages(db, "B-3", "INSTAY")

    assert result == {"cancelled_ids": [2], "count": 1}
    assert compatible.status == "PENDING"
    assert incompatible.status == "CANCELLED"
    assert isinstance(incompatible.updated_at, datetime)
    db.commit.assert_called_once()


def test_cancel_conflicting_messages_does_not_commit_when_nothing_cancelled(queue_module):
    item = types.SimpleNamespace(
        id=1,
        status="PENDING",
        template=types.SimpleNamespace(stage=["INSTAY"]),
    )
    query = MagicMock()
    query.join.return_value = query
    query.filter.return_value = query
    query.all.return_value = [item]
    db = MagicMock()
    db.query.return_value = query

    result = queue_module.cancel_conflicting_messages(db, "B-4", "INSTAY")

    assert result == {"cancelled_ids": [], "count": 0}
    db.commit.assert_not_called()


def test_update_send_time_returns_none_and_rolls_back_on_operational_error(queue_module):
    from sqlalchemy.exc import OperationalError

    db = MagicMock()
    db.execute.side_effect = OperationalError("statement", {}, Exception("lock timeout"))

    result = queue_module.update_send_time(
        db, 1, "B-5", "WELCOME", datetime(2026, 1, 1, 12, 0)
    )

    assert result is None
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_update_send_time_returns_existing_record_when_no_row_updated(queue_module):
    db = MagicMock()
    execution_result = MagicMock()
    execution_result.scalar_one_or_none.return_value = None
    db.execute.side_effect = [None, execution_result]

    existing = object()
    query = MagicMock()
    query.join.return_value = query
    query.filter.return_value = query
    query.first.return_value = existing
    db.query.return_value = query

    result = queue_module.update_send_time(
        db, 1, "B-6", "WELCOME", datetime(2026, 1, 1, 12, 0)
    )

    assert result is existing
    db.commit.assert_called_once()


def test_update_send_time_fetches_updated_record_by_id(queue_module):
    db = MagicMock()
    execution_result = MagicMock()
    execution_result.scalar_one_or_none.return_value = 99
    db.execute.side_effect = [None, execution_result]

    updated = object()
    query = MagicMock()
    query.filter.return_value.first.return_value = updated
    db.query.return_value = query

    result = queue_module.update_send_time(
        db, 1, "B-7", "WELCOME", datetime(2026, 1, 1, 12, 0)
    )

    assert result is updated
    db.commit.assert_called_once()
