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


def test_greenhouse_client_parses_jobs():
    def handler(request):
        assert "content=true" in str(request.url)
        return httpx.Response(200, json={"jobs": [
            {"id": 42, "title": "Data Engineer", "location": {"name": "Remote - US"},
             "departments": [{"name": "Data"}], "content": "&lt;p&gt;Hello&lt;/p&gt;"}]})
    fetch = greenhouse.fetch_board("acme", transport=_mock_transport(handler))
    assert len(fetch.postings) == 1
    assert fetch.postings[0].source_posting_id == "42"
    assert fetch.postings[0].department == "Data"


def test_lever_client_paginates_and_prefers_plain_text():
    pages = {
        0: [{"id": f"id-{i}", "text": "Eng", "categories": {"location": "NYC", "department": "Eng"},
             "descriptionPlain": "plain", "description": "<p>html</p>"} for i in range(100)],
        100: [{"id": "id-100", "text": "Eng", "categories": {}, "descriptionPlain": "last"}],
    }
    def handler(request):
        skip = int(request.url.params.get("skip", "0"))
        return httpx.Response(200, json=pages.get(skip, []))
    fetch = lever.fetch_board("acme", transport=_mock_transport(handler))
    assert len(fetch.postings) == 101
    assert fetch.postings[0].description_raw == "plain"
