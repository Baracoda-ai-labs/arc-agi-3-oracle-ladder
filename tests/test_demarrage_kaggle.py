"""D (CW-446 / CW-455) : cellule de vérification du démarrage Kaggle — 1re inférence exigée, serveur mort détecté,
durée de jeu réduite de l'attente, journal ; variante R0 = Franzen pur + ces cellules, sans notre cellule Chrysalide."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

from scripts.arc3 import demarrage_kaggle as DK
from scripts.arc3 import faire_notebook_S as fab


class _H(BaseHTTPRequestHandler):
    vide = False

    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200 if self.path == "/health" else 404)
        self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        corps = json.loads(self.rfile.read(n))
        assert corps["model"] == "flashnext"
        rep = {"choices": [{"message": {"content": "" if _H.vide else "OK"}}],
               "usage": {"completion_tokens": 0 if _H.vide else 1}}
        b = json.dumps(rep).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


def _serveur():
    s = HTTPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def _ns(tmp_path, port, proc, debut):
    log = tmp_path / "serve.log"
    log.write_text("Loading safetensors checkpoint shards: 100% 38/38 [00:40<00:00]\n")
    return {"Path": Path, "WORKING_DIR": tmp_path, "TRUE_SUBMISSION": True, "SERVED_MODEL_PORT": port,
            "SERVED_MODEL_NAME": "flashnext", "LOG": str(log), "proc": proc, "NOTEBOOK_START_TIME": debut,
            "bm": SimpleNamespace(solver=SimpleNamespace(max_runtime_s_per_game=532 * 60))}


def _journal(tmp_path):
    return [json.loads(x) for x in (tmp_path / "chrysalide_demarrage.jsonl").read_text().splitlines()]


def test_premiere_inference_et_duree_reduite(tmp_path):
    s = _serveur()
    g = _ns(tmp_path, s.server_port, SimpleNamespace(poll=lambda: None), time.time() - 3600)  # 1 h déjà attendue
    exec(compile(DK.AVANT, "avant", "exec"), g)  # noqa: S102
    exec(compile(DK.APRES, "apres", "exec"), g)  # noqa: S102
    j = _journal(tmp_path)
    etapes = [x["etape"] for x in j]
    assert etapes[0] == "environnement" and "chargement" in etapes and "sante" in etapes
    assert "premiere_inference" in etapes and etapes[-2:] == ["partie", "fin"]
    partie = next(x for x in j if x["etape"] == "partie")
    assert partie["pret"] is True and partie["duree_jeu_s"] < 532 * 60  # 9 h − 1 h − marge < 8 h 52
    assert next(x for x in j if x["etape"] == "chargement")["fait"] == 38
    s.shutdown()


def test_reponse_vide_n_est_pas_une_inference(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRYS_PATIENCE_S", "1")
    _H.vide = True
    s = _serveur()
    try:
        g = _ns(tmp_path, s.server_port, SimpleNamespace(poll=lambda: None), time.time())
        exec(compile(DK.AVANT, "avant", "exec"), g)  # noqa: S102
    finally:
        _H.vide = False
        s.shutdown()
    etapes = [x["etape"] for x in _journal(tmp_path)]
    assert "premiere_inference" not in etapes and "echec" in etapes


def test_serveur_mort(tmp_path):
    g = _ns(tmp_path, 1, SimpleNamespace(poll=lambda: 1, returncode=1), time.time())
    exec(compile(DK.AVANT, "avant", "exec"), g)  # noqa: S102
    etapes = [x["etape"] for x in _journal(tmp_path)]
    assert "serveur_mort" in etapes and "echec" in etapes and "premiere_inference" not in etapes


def test_variante_r0(tmp_path):
    fab.main("R0", tmp_path)
    nb = json.loads((tmp_path / "notebook_R0.ipynb").read_text())
    src = ["".join(c["source"]) for c in nb["cells"]]
    i = next(k for k, x in enumerate(src) if "print('Starting benchmark...')" in x)
    assert "vérification du démarrage" in src[i - 1] and "fin de partie" in src[i + 1]
    assert not any("CHRYSALIDE — variante" in x and "_CHRYS_ARCHIVE" in x for x in src)  # Franzen pur
