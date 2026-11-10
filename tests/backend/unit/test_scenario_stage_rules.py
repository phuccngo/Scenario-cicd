import pytest

from scenario_stage_rules import normalize_stage, is_stage_compatible


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("PREARRIVAL", "PREARRIVAL"),
        ("instay", "INSTAY"),
        (" CHECKOUT ", "INSTAY"),
        ("poststay", "POSTSTAY"),
        ("", None),
        ("   ", None),
        (None, None),
        (123, "123"),
    ],
)
def test_normalize_stage(value, expected):
    assert normalize_stage(value) == expected


@pytest.mark.parametrize(
    ("current_stage", "template_stages", "expected"),
    [
        ("PREARRIVAL", ["PREARRIVAL"], True),
        ("INSTAY", ["PREARRIVAL", "INSTAY"], True),
        ("POSTSTAY", ["PREARRIVAL", "INSTAY"], False),
        ("CHECKOUT", ["INSTAY"], True),
        ("INSTAY", "instay", True),
        ("INSTAY", "PREARRIVAL", False),
        ("INSTAY", None, True),
        ("INSTAY", [], True),
        ("INSTAY", ["", None, "  "], True),
        (None, ["PREARRIVAL"], True),
        ("", ["PREARRIVAL"], True),
    ],
)
def test_is_stage_compatible(current_stage, template_stages, expected):
    assert is_stage_compatible(current_stage, template_stages) is expected


def test_is_stage_compatible_accepts_iterable_of_stage_values():
    assert is_stage_compatible("INSTAY", ("PREARRIVAL", "CHECKOUT")) is True


def test_is_stage_compatible_does_not_match_unlisted_stage():
    assert is_stage_compatible("POSTSTAY", ["PREARRIVAL", "INSTAY"]) is False
