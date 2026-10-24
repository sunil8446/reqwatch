"""Unit tests: cleaning, hashing, schema snapshot, DB-size projection, clients."""
import httpx

from reqwatch.cleaning import html_to_cleaned_text
from reqwatch.clients import greenhouse, lever
from reqwatch.db import project_months_until_limit
from reqwatch.hashing import content_hash, schema_snapshot


def test_greenhouse_double_escaped_html_cleans():
    raw = "&lt;p&gt;Build &lt;b&gt;data&lt;/b&gt; pipelines&lt;/p&gt;"
    assert html_to_cleaned_text(raw) == "Build data pipelines"


def test_cleaning_collapses_whitespace_and_tags():
    assert html_to_cleaned_text("<p>Hello</p><p>World</p>") == "Hello\nWorld"
    assert html_to_cleaned_text("") == ""
    assert html_to_cleaned_text(None) == ""


def test_hash_stable_under_whitespace_and_case_noise():
    a = content_hash("Data Engineer", "Remote", "Data", "<p>Build   things</p>".replace("<p>", "").replace("</p>", ""))
    b = content_hash("data engineer", "remote", "data", "build things")
    assert a == b


def test_hash_changes_on_real_wording_change():
    a = content_hash("Data Engineer", "Remote", "Data", "Build pipelines in Python")
    b = content_hash("Data Engineer", "Remote", "Data", "Build pipelines in Rust")
    assert a != b


def test_schema_snapshot_names_only_sorted():
    digest, names = schema_snapshot([{"b": 1, "a": 2}, {"c": 3}])
    assert names == ["a", "b", "c"]
    digest2, _ = schema_snapshot([{"a": 9, "b": 8, "c": 7}])
    assert digest == digest2  # values never affect the snapshot


def test_projection_none_until_growth_measured():
    assert project_months_until_limit(100_000_000, None) is None
    assert project_months_until_limit(100_000_000, 0) is None
    # (1 GiB - 500 MB) at 10 MB/run, 1 run/day -> ~1.9 months
    months = project_months_until_limit(500_000_000, 10_000_000, runs_per_day=1)
    assert months is not None and 1.5 < months < 2.5


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def test_title_filter_keeps_tech_cuts_commercial():
    from reqwatch.title_filter import title_keeps
    assert title_keeps("Senior Data Engineer")
    assert title_keeps("ML Platform Engineer")
    assert title_keeps("Site Reliability Engineer")
    assert not title_keeps("Accountant")
    assert not title_keeps("Account Manager, Starlink Enterprise")
    assert not title_keeps("Additive Manufacturing Engineer (Raptor)")
    assert not title_keeps("Financial Analyst")
    assert not title_keeps("Product Manager, Data Platform")


def test_greenhouse_two_stage_filter_before_content():
    content_calls = []
    def handler(request):
        url = str(request.url)
        if url.endswith("/jobs"):
            return httpx.Response(200, json={"jobs": [
                {"id": 42, "title": "Data Engineer", "location": {"name": "Remote - US"},
                 "departments": [{"name": "Data"}]},
                {"id": 43, "title": "Accountant", "location": {"name": "NYC"},
                 "departments": [{"name": "Finance"}]}]})
        content_calls.append(url)
        return httpx.Response(200, json={
            "id": 42, "title": "Data Engineer", "location": {"name": "Remote - US"},
            "departments": [{"name": "Data"}], "content": "&lt;p&gt;Hello&lt;/p&gt;"})
    fetch = greenhouse.fetch_board("acme", transport=_mock_transport(handler))
    assert fetch.postings_listed == 2
    assert len(fetch.postings) == 1
    assert fetch.postings[0].source_posting_id == "42"
    assert len(content_calls) == 1 and content_calls[0].endswith("/jobs/42")


def test_lever_client_paginates_and_prefers_plain_text():
    pages = {
        0: [{"id": f"id-{i}", "text": "Software Engineer", "categories": {"location": "NYC", "department": "Eng"},
             "descriptionPlain": "plain", "description": "<p>html</p>"} for i in range(100)],
        100: [{"id": "id-100", "text": "Software Engineer", "categories": {}, "descriptionPlain": "last"}],
    }
    def handler(request):
        skip = int(request.url.params.get("skip", "0"))
        return httpx.Response(200, json=pages.get(skip, []))
    fetch = lever.fetch_board("acme", transport=_mock_transport(handler))
    assert len(fetch.postings) == 101
    assert fetch.postings[0].description_raw == "plain"


def test_greenhouse_skips_content_fetch_when_unchanged():
    detail_calls = []
    def handler(request):
        url = str(request.url)
        if url.endswith("/jobs"):
            return httpx.Response(200, json={"jobs": [
                {"id": 1, "title": "Data Engineer", "updated_at": "2026-10-20T00:00:00Z",
                 "location": {"name": "NYC"}, "departments": []},
                {"id": 2, "title": "ML Engineer", "updated_at": "2026-10-21T00:00:00Z",
                 "location": {"name": "SF"}, "departments": []}]})
        detail_calls.append(url)
        return httpx.Response(200, json={"id": 2, "title": "ML Engineer",
            "location": {"name": "SF"}, "departments": [], "content": "&lt;p&gt;x&lt;/p&gt;"})
    known = {"1": ("Data Engineer", "2026-10-20T00:00:00Z")}
    fetch = greenhouse.fetch_board("acme", transport=_mock_transport(handler), known=known)
    assert fetch.content_fetches_skipped == 1
    assert len(detail_calls) == 1 and detail_calls[0].endswith("/jobs/2")
    by_id = {p.source_posting_id: p for p in fetch.postings}
    assert by_id["1"].unchanged and by_id["1"].source_updated_at == "2026-10-20T00:00:00Z"
    assert not by_id["2"].unchanged


def test_ollama_provider_uses_schema_constrained_format():
    import json as _json
    import httpx as _httpx
    from reqwatch.providers.ollama import OllamaProvider, format_schema

    captured = {}
    def handler(request):
        captured.update(_json.loads(request.content))
        return _httpx.Response(200, json={
            "message": {"content": _json.dumps({
                "skills": ["Python"], "seniority": "senior",
                "role_family": "data_engineering", "required_years": 5,
                "tech_stack": ["dbt"], "work_mode": "remote", "location": "NYC"})},
            "prompt_eval_count": 500, "eval_count": 60})
    provider = OllamaProvider("qwen2.5:3b", transport=_httpx.MockTransport(handler))
    out = provider.extract("posting body")
    fmt = captured["format"]
    assert isinstance(fmt, dict) and fmt == format_schema()
    assert fmt["additionalProperties"] is False
    assert set(fmt["required"]) == set(fmt["properties"].keys())
    assert out.result.role_family == "data_engineering"
    assert (out.input_tokens, out.output_tokens) == (500, 60)
