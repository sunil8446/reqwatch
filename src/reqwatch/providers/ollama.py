"""Ollama provider (local models, $0). Talks to a running Ollama server's
/api/chat with JSON-SCHEMA CONSTRAINED output: the Pydantic schema is
passed via the `format` parameter, so the decoder itself is restricted to
schema-shaped JSON (Sunil's Phase 2 amendment, 2026-10-24). Token counts
come from Ollama's own response fields (prompt_eval_count / eval_count) —
measured, not estimated."""
from __future__ import annotations

import json
import os

import httpx
from pydantic import ValidationError

from ..extraction.prompt import PROMPT_VERSION, build_messages
from .base import ExtractionOutput, ExtractionResult


def format_schema() -> dict:
    """The ExtractionResult JSON schema, tightened for constrained decoding:
    every property required (nulls allowed via the schema's own anyOf) and
    no additional properties."""
    schema = ExtractionResult.model_json_schema()
    schema["required"] = list(schema.get("properties", {}).keys())
    schema["additionalProperties"] = False
    return schema


class OllamaProvider:
    name = "ollama"
    prompt_version = PROMPT_VERSION

    def __init__(self, model: str, *, base_url: str | None = None, timeout: float = 600.0,
                 transport: httpx.BaseTransport | None = None):
        self.model = model
        self.base_url = base_url or os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        self.timeout = timeout
        self.transport = transport

    def extract(self, cleaned_text: str, *, retry_hint: str | None = None) -> ExtractionOutput:
        payload = {
            "model": self.model,
            "messages": build_messages(cleaned_text, retry_hint),
            "format": format_schema(),
            "stream": False,
            "options": {"temperature": 0},
        }
        with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
            resp = client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
        data = resp.json()
        raw = (data.get("message") or {}).get("content", "")
        try:
            parsed = json.loads(raw)
            result = ExtractionResult.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as exc:
            # Surface as ValueError with the raw text attached so the runner
            # can retry once with the hint, then dead-letter with evidence.
            err = ValueError(f"invalid extraction output: {exc}")
            err.raw_text = raw  # type: ignore[attr-defined]
            raise err from exc
        return ExtractionOutput(
            result=result,
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
            raw_text=raw,
        )
