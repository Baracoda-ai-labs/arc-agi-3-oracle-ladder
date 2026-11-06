"""Vérificateurs exécutables (plan 3.1, T0.5). Aucun LLM : extraction JSON stricte, comparaison typée, pytest en sous-processus."""
import json
import re
import resource
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

STATUSES = ("correct", "incorrect", "unextractable", "constraint_violation")
TIMEOUT_S = 30


@dataclass
class Verdict:
    status: str
    details: dict = field(default_factory=dict)


class Unextractable(ValueError):
    pass


def _no_dup(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise Unextractable(f"clé répétée : {keys}")
    return dict(pairs)


def extract(output: str):
    """La sortie entière doit être UN objet JSON {"reponse": ...}. Tolérés seulement : espaces,
    un bloc <think>…</think> initial, une clôture ```json … ``` autour de l'objet."""
    if not isinstance(output, str):
        raise Unextractable("sortie non textuelle")
    s = re.sub(r"^\s*<think>.*?</think>", "", output, count=1, flags=re.DOTALL).strip()
    m = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?\s*```", s, flags=re.DOTALL)
    if m:
        s = m.group(1).strip()
    if "\n" in s:
        raise Unextractable("plusieurs lignes")
    try:
        obj = json.loads(s, object_pairs_hook=_no_dup)
    except json.JSONDecodeError as e:
        raise Unextractable(f"JSON invalide : {e.msg}") from None
    if not isinstance(obj, dict) or set(obj) != {"reponse"}:
        raise Unextractable("objet attendu avec la seule clé 'reponse'")
    return obj["reponse"]


def _norm_str(s: str) -> str:
    return " ".join(unicodedata.normalize("NFC", s).split()).casefold()


def check_constraints(task: dict, trace: dict | None) -> list[str]:
    """Contraintes d'exécution : task['constraints'] = {forbidden_tools, max_tool_calls, max_tokens} (toutes optionnelles).
    trace = {"tool_calls": [{"tool": id, ...}], "tokens": n}."""
    c, trace = task.get("constraints") or {}, trace or {}
    calls = trace.get("tool_calls", [])
    bad = []
    used = {k["tool"] for k in calls}
    if forbidden := used & set(c.get("forbidden_tools", [])):
        bad.append(f"outil interdit : {sorted(forbidden)}")
    if "max_tool_calls" in c and len(calls) > c["max_tool_calls"]:
        bad.append(f"appels d'outils {len(calls)} > {c['max_tool_calls']}")
    if "max_tokens" in c and trace.get("tokens", 0) > c["max_tokens"]:
        bad.append(f"tokens {trace['tokens']} > {c['max_tokens']}")
    return bad


def _limits():
    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT_S, TIMEOUT_S))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))  # 1 Mo écrit au plus


def run_pytest(code: str, fonction: str, tests: list) -> dict:
    """Exécute le code candidat contre les tests dans un répertoire temporaire, processus Python isolé (-I), timeout 30 s."""
    with tempfile.TemporaryDirectory() as d:
        Path(d, "candidat.py").write_text(code, encoding="utf-8")
        Path(d, "test_candidat.py").write_text(
            "import pytest\nfrom candidat import " + fonction + " as f\n\n"
            f"@pytest.mark.parametrize('x,y', {tests!r})\n"
            "def test_cas(x, y):\n    assert f(x) == y\n", encoding="utf-8")
        cmd = [sys.executable, "-I", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "--rootdir", d, d]
        try:
            r = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=TIMEOUT_S, preexec_fn=_limits, check=False)
        except subprocess.TimeoutExpired:
            return {"ok": False, "raison": "timeout"}
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    return {"ok": r.returncode == 0, "code_retour": r.returncode, "pytest": tail[:200]}


def verify(task: dict, output: str, trace: dict | None = None) -> Verdict:
    if bad := check_constraints(task, trace):
        return Verdict("constraint_violation", {"violations": bad})
    try:
        ans = extract(output)
    except Unextractable as e:
        return Verdict("unextractable", {"raison": str(e)})
    vid, exp = task["verifier_id"], task["expected"]
    if vid == "json_int":
        if isinstance(ans, bool) or not isinstance(ans, int):
            return Verdict("unextractable", {"raison": f"entier attendu, reçu {type(ans).__name__}"})
        return Verdict("correct" if ans == exp else "incorrect", {"reponse": ans})
    if vid == "json_str":
        if not isinstance(ans, str) or not ans.strip():
            return Verdict("unextractable", {"raison": "chaîne non vide attendue"})
        return Verdict("correct" if _norm_str(ans) == _norm_str(exp) else "incorrect", {"reponse": ans})
    if vid == "pytest_fn":
        if not isinstance(ans, str) or len(re.findall(rf"^def {exp['fonction']}\(", ans, flags=re.MULTILINE)) != 1:
            return Verdict("unextractable", {"raison": f"code définissant {exp['fonction']} une seule fois attendu"})
        r = run_pytest(ans, exp["fonction"], exp["tests"])
        return Verdict("correct" if r["ok"] else "incorrect", r)
    raise ValueError(f"vérificateur inconnu : {vid}")
