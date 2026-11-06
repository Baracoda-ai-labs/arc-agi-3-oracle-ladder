# SPDX-License-Identifier: MIT-0
"""F (CW-429) : contrôle de soumission sans GPU. Contrôle positif : le 0,00 d'e1b658 (CW-427) doit sortir KO sur les
bons points ; un passage normal (lignes réelles de R12 et du serve.log du pod) doit sortir OK."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/arc3"))
import controle_kaggle as C

JEUX_OK = ["  ar25-0c556536: score=41.67, levels=5.0/8, actions=158, tokens=110697",
           "  sc25-635fd71a: score=0.00, levels=0.0/6, actions=80, tokens=57850"]
JEUX_ZERO = [f"  ar{i:02d}-0c556536: score=0.00, levels=0.0/8, actions=0, tokens=0" for i in range(25)]
SERVE_OK = ["[2026-10-17 12:23:47] Breakable CUDA graph is incompatible with multimodal model; disabling prefill CUDA graph.",
            "[2026-10-17 12:29:16] INFO:     Application startup complete.",
            "[2026-10-17 12:29:24] The server is fired up and ready to roll!"]


def test_zero_e1b658_ko():
    logs = ["Environment: Latest Container Image", "  690s ...",
            "DEADLINE at 721s from notebook start; releasing the benchmark with the server still loading",
            "requests.exceptions.ConnectionError: [Errno 111] Connection refused"] + JEUX_ZERO
    points, verdict = C.controler(logs)
    assert verdict.startswith("KO")
    assert not points["serveur"]["ok"] and "DEADLINE at 721s" in points["serveur"]["detail"]
    assert not points["jeux"]["ok"] and "25 à 0 action" in points["jeux"]["detail"]
    assert not points["erreurs"]["ok"]
    assert points["environnement"]["ok"] and points["environnement"]["alerte"]  # CW-432 : la version à 28,21 l'affiche aussi


def test_passage_normal_ok():
    logs = ["Connection refused pendant le chargement", "\nREADY after 336s -> http://127.0.0.1:8001/v1",
            "Pin to original environment (2026-05-26)", "Starting benchmark...",
            "  ar25-0c556536: score=0.00, levels=0.0/8, actions=0, tokens=0"] + JEUX_OK  # résumé périodique ancien
    points, verdict = C.controler(logs, SERVE_OK)
    assert verdict == "OK", points
    assert "336 s" in points["serveur"]["detail"]  # le refus AVANT le « prêt » n'est pas une erreur


def test_serve_jamais_pret_et_environnement_inconnu():
    serve = SERVE_OK[:2] + ["[2026-10-17 20:00:00] Loading safetensors checkpoint shards: 37% Completed"]
    points, _ = C.controler(JEUX_OK, serve)
    assert not points["serveur"]["ok"] and "jamais « fired up »" in points["serveur"]["detail"]
    assert points["environnement"].get("alerte") and "non lu" in points["environnement"]["detail"]
    points, _ = C.controler(JEUX_OK, serve, texte_env="Environment: Pin to original environment (2026-05-26)")
    assert points["environnement"]["ok"]


def test_format_json_kaggle_et_cli(tmp_path, capsys):
    f = tmp_path / "logs.log"
    f.write_text(json.dumps([{"stream_name": "stdout", "time": 1.0, "data": "\nREADY after 300s -> x\n"},
                             {"stream_name": "stdout", "time": 2.0, "data": "Pin to original environment\n"},
                             {"stream_name": "stdout", "time": 3.0, "data": "\n".join(JEUX_OK) + "\n"}]))
    assert C.main([str(f)]) == 0
    assert "VERDICT : OK" in capsys.readouterr().out
    f.write_text("CUDA error: an illegal memory access was encountered\n" + "\n".join(JEUX_OK))
    assert C.main([str(f)]) == 1


def test_temoins_franzen():
    temoin = "  vc33-12ab34cd: score=0.00, levels=0.0/7, actions=12, tokens=0"
    points, verdict = C.controler(["\nREADY after 300s -> x"] + JEUX_OK + [temoin])
    assert verdict == "KO (temoins)" and "vc33-12ab34cd" in points["temoins"]["detail"]


MOTEUR_OK = ["moteur seul : TRUE_SUBMISSION=False",
             "paquet conforme : global a6f847da0000 ; adaptateur 1234abcd5678ef90",
             "jeux joués 20 / 20 ; niveaux 7 ; erreurs 0 ; 410.3 min"]


def test_moteur_seul(tmp_path):
    points, verdict = C.controler(MOTEUR_OK, moteur_seul=True)  # CPU : pas de serveur, pas de résumé Franzen
    assert verdict == "OK", points
    assert C.controler(MOTEUR_OK[:1] + MOTEUR_OK[2:], moteur_seul=True)[1] == "KO (paquet)"
    assert C.controler(MOTEUR_OK[:2] + ["jeux joués 18 / 20 ; niveaux 7 ; erreurs 2 ; 400 min"],
                       moteur_seul=True)[1] == "KO (jeux)"
    assert C.controler(MOTEUR_OK[:2] + ["jeux joués 20 / 20 ; niveaux 0 ; erreurs 0 ; 400 min"],
                       moteur_seul=True)[1] == "KO (jeux)"
    assert C.controler(MOTEUR_OK[:2] + ["RuntimeError: GARDE TÉMOINS : ['vc33-1'] ne doivent JAMAIS être joués"],
                       moteur_seul=True)[1] == "KO (jeux, temoins)"
    pil = [{"jeu": "ar25-0c556536", "niveaux": 2}, {"jeu": "ft09-0d8bbf25", "saute": "budget du carnet"}]
    points, verdict = C.controler(MOTEUR_OK, moteur_seul=True, pilote=pil)
    assert verdict == "KO (jeux)" and "ft09-0d8bbf25" in points["jeux"]["detail"]
    f, g = tmp_path / "logs.txt", tmp_path / "pilote.jsonl"
    f.write_text("\n".join(MOTEUR_OK))
    g.write_text(json.dumps({"jeu": "tu93-00000000", "niveaux": 0}) + "\n")
    assert C.main([str(f), "--moteur-seul", "--pilote", str(g)]) == 1  # un témoin dans le journal du pilote


def test_demarrage_r0():
    ok = ["CHRYSALIDE démarrage environnement {'t_s': 0.1, 'python': '3.12.1', 'python_312': True}",
          "CHRYSALIDE démarrage premiere_inference {'t_s': 412.3, 'latence_s': 1.8, 'jetons': 5}",
          "\nREADY after 400s -> x", "Pin to original environment"] + JEUX_OK
    points, verdict = C.controler(ok)
    assert verdict == "OK", points
    assert "412.3" in points["demarrage"]["detail"]
    sans = [x for x in ok if "premiere_inference" not in x]
    assert C.controler(sans)[1] == "KO (demarrage)"
    py311 = [x.replace("True", "False") if "environnement" in x else x for x in ok]
    assert "3.12" in C.controler(py311)[0]["demarrage"]["detail"]
    mort = [*ok, "CHRYSALIDE démarrage serveur_mort {'t_s': 900, 'code': -9}"]
    assert C.controler(mort)[1] == "KO (demarrage)"
    journal = [{"etape": "environnement", "python_312": True}, {"etape": "premiere_inference", "t_s": 300.0, "latence_s": 2}]
    assert C.controler([x for x in ok if "CHRYSALIDE" not in x], journal=journal)[1] == "OK"
    assert "sans objet" in C.controler(["\nREADY after 400s -> x"] + JEUX_OK)[0]["demarrage"]["detail"]
