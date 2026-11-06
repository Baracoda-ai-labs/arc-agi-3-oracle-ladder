"""Échoue si du code importe une API LLM payante."""
import pathlib
import re


def test_no_paid_llm_api():
    bad = re.compile(r"^\s*(import|from)\s+(anthropic|openai|mistralai|cohere|google\.genai)\b", re.MULTILINE)
    hits = [str(p) for p in pathlib.Path("chrysalide").rglob("*.py") if bad.search(p.read_text())]
    assert not hits, f"API LLM payante importée dans : {hits}"
