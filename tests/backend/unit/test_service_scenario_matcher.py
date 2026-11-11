from types import SimpleNamespace
import pytest
import service_scenario_matcher as matcher

@pytest.fixture(autouse=True)
def disable_embeddings(monkeypatch):
    monkeypatch.setattr(matcher._EmbeddingBackend, "encode",
                        classmethod(lambda cls, texts: None))

def tpl(code, name, goal="", key_points=None, wording=""):
    return SimpleNamespace(code=code, name=name, creative_context={
        "goal": goal, "key_points": key_points or [], "example_wording": wording,
    })

def test_tokenize_removes_stopwords_and_short_tokens():
    assert matcher._tokenize("DỊCH VỤ và Spa ở 2") == ["dịch", "vụ", "spa"]

def test_tokenize_empty():
    assert matcher._tokenize("") == []
    assert matcher._tokenize(None) == []

def test_bm25_prefers_relevant_document():
    bm25 = matcher._BM25([
        matcher._tokenize("massage thư giãn spa"),
        matcher._tokenize("đưa đón sân bay"),
    ])
    scores = bm25.score_all(matcher._tokenize("massage spa"))
    assert scores[0] > scores[1]

def test_scenario_text_uses_dynamic_creative_context():
    item = tpl("S1", "Tên", "Mục tiêu", ["điểm một", "điểm hai"], "Cách nói")
    assert matcher._scenario_text(item) == "Tên Mục tiêu điểm một điểm hai Cách nói"

def test_service_text_combines_fields():
    service = {"serviceName": "Massage", "serviceNameEn": "Body massage",
               "description": "Thư giãn", "serviceCategory": "Spa"}
    assert matcher._service_text(service) == "Massage Body massage Thư giãn Spa"

def test_fallback_template_excluded_when_regular_candidate_exists():
    obj = matcher.ServiceScenarioMatcher([
        tpl("SALE_SPA", "Massage spa"),
        tpl("SALE_SCENARIO_TEMPLATE", "Fallback"),
    ])
    assert [x.code for x in obj.templates] == ["SALE_SPA"]

def test_fallback_remains_when_it_is_only_template():
    obj = matcher.ServiceScenarioMatcher([tpl("SALE_SCENARIO_TEMPLATE", "Fallback")])
    assert [x.code for x in obj.templates] == ["SALE_SCENARIO_TEMPLATE"]

def test_best_match_selects_lexically_relevant_template():
    obj = matcher.ServiceScenarioMatcher([
        tpl("SALE_SPA", "Massage spa thư giãn"),
        tpl("SALE_AIRPORT", "Đưa đón sân bay"),
    ])
    code, score = obj._best_match({"serviceName": "Massage spa"})
    assert code == "SALE_SPA"
    assert score > 0

def test_unmatched_service_uses_fallback(monkeypatch):
    monkeypatch.setattr(matcher, "_MATCH_THRESHOLD", 0.99)
    obj = matcher.ServiceScenarioMatcher([tpl("SALE_SPA", "Massage spa")])
    service = {"serviceName": "Thuê xe đạp"}
    assert obj.match_services([service]) == {"SALE_SCENARIO_TEMPLATE": [service]}

def test_empty_templates_use_fallback():
    obj = matcher.ServiceScenarioMatcher([])
    service = {"serviceName": "Bất kỳ"}
    assert obj.match_services([service]) == {"SALE_SCENARIO_TEMPLATE": [service]}

def test_embedding_returns_none_without_numpy(monkeypatch):
    monkeypatch.setattr(matcher, "np", None)
    assert matcher._EmbeddingBackend.encode(["hello"]) is None
