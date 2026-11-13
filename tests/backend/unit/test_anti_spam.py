from datetime import datetime

import anti_spam


class Message:
    def __init__(self, send_time, priority=0):
        self.send_time = send_time
        self.priority = priority


def test_default_config_values():
    assert anti_spam.DEFAULT_CONFIG == {
        "quiet_hours_start": 6.0,
        "quiet_hours_end": 22.5,
        "min_interval_minutes": 5,
        "buffer_days": 30,
    }


def test_is_quiet_hour_before_start():
    config = anti_spam.DEFAULT_CONFIG
    assert anti_spam.is_quiet_hour(datetime(2026, 1, 1, 5, 59), config) is True


def test_is_quiet_hour_at_start_is_not_quiet():
    config = anti_spam.DEFAULT_CONFIG
    assert anti_spam.is_quiet_hour(datetime(2026, 1, 1, 6, 0), config) is False


def test_is_quiet_hour_before_end_is_not_quiet():
    config = anti_spam.DEFAULT_CONFIG
    assert anti_spam.is_quiet_hour(datetime(2026, 1, 1, 22, 30), config) is False


def test_is_quiet_hour_at_end():
    config = anti_spam.DEFAULT_CONFIG
    assert anti_spam.is_quiet_hour(datetime(2026, 1, 1, 22, 31), config) is True


def test_normalize_to_segment_moves_early_time_to_start():
    value = datetime(2026, 1, 1, 5, 12, 45)
    result = anti_spam.normalize_to_segment(value, anti_spam.DEFAULT_CONFIG)
    assert result == datetime(2026, 1, 1, 6, 0, 0)


def test_normalize_to_segment_preserves_time_inside_allowed_window():
    value = datetime(2026, 1, 1, 12, 34, 56)
    assert anti_spam.normalize_to_segment(value, anti_spam.DEFAULT_CONFIG) == value


def test_normalize_to_segment_uses_fractional_start_hour():
    config = {
        "quiet_hours_start": 6.5,
        "quiet_hours_end": 22.5,
        "min_interval_minutes": 5,
        "buffer_days": 30,
    }
    value = datetime(2026, 1, 1, 6, 10, 20)
    assert anti_spam.normalize_to_segment(value, config) == datetime(2026, 1, 1, 6, 30, 0)


def test_apply_rules_sorts_by_priority_then_time():
    messages = [
        Message(datetime(2026, 1, 1, 10, 10), priority=1),
        Message(datetime(2026, 1, 1, 10, 0), priority=5),
        Message(datetime(2026, 1, 1, 11, 0), priority=1),
    ]

    result = anti_spam.apply_anti_spam_rules(messages)

    assert result[0].priority == 5
    assert result[1].send_time == datetime(2026, 1, 1, 10, 10)
    assert result[2].send_time == datetime(2026, 1, 1, 11, 0)


def test_apply_rules_moves_conflicting_message_forward_when_no_earlier_slot():
    first = Message(datetime(2026, 1, 1, 10, 0), priority=10)
    second = Message(datetime(2026, 1, 1, 10, 2), priority=1)

    result = anti_spam.apply_anti_spam_rules([first, second])

    assert len(result) == 2
    assert first.send_time == datetime(2026, 1, 1, 10, 0)
    assert second.send_time == datetime(2026, 1, 1, 10, 5)


def test_apply_rules_uses_supplied_config_without_mutating_defaults():
    custom = {
        "quiet_hours_start": 7.0,
        "quiet_hours_end": 21.0,
        "min_interval_minutes": 10,
        "buffer_days": 7,
    }
    original_defaults = anti_spam.DEFAULT_CONFIG.copy()
    message = Message(datetime(2026, 1, 1, 6, 0), priority=1)

    result = anti_spam.apply_anti_spam_rules([message], custom)

    assert result[0].send_time == datetime(2026, 1, 1, 7, 0)
    assert anti_spam.DEFAULT_CONFIG == original_defaults
