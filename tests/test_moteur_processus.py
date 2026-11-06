# SPDX-License-Identifier: MIT-0
"""CHRYS_MOTEUR_PROCESSUS (moteur_processus.py) : F-C2 drapeau éteint ; même partie au point près avec le moteur dans un
ouvrier ; débit d'un autre fil pendant 2 s de CPU du moteur (LE test du correctif) ; délai dur ; envoi incrémental ;
chaîne réelle MoteurC sur sk01 = même plan qu'en local."""
import json
import os
import threading
import time

import pytest
from test_moteur import Factice, Ligne, _eteindre, _scenario

from chrysalide.arc3 import branche
from chrysalide.arc3.moteur import NOMS, MoteurFormel, porte
from chrysalide.arc3.moteur_processus import MoteurDistant


class Lent(MoteurFormel):
    """proposer = `secondes` de CPU en Python pur (tient le GIL), puis None. Compte ses appels (état de l'ouvrier)."""
    def __init__(self, secondes=2.0):
        self.secondes, self.appels, self.infos = secondes, 0, {}

    def proposer(self, historique):
        self.appels += 1
        t0, x = time.process_time(), 0
        while time.process_time() - t0 < float(os.environ.get("CHRYS_TEST_CPU_S", self.secondes)):
            for i in range(2000):
                x += i * i
        self.infos = {"cpu_s": time.process_time() - t0, "appels": self.appels,
                      "n": {k: len(v) for k, v in historique.items()}, "pid": os.getpid()}


class Dort(MoteurFormel):
    def __init__(self):
        self.infos = {}

    def proposer(self, historique):
        time.sleep(float(os.environ.get("CHRYS_TEST_DORT_S", "0")))
        self.infos = {"cpu_s": 0.0, "marque": os.environ.get("CHRYS_TEST_MARQUE")}
        return [{"action": "RIGHT"}], {"etat": {}, "regles": []}


def _hist(n):
    g = [[0] * 64 for _ in range(64)]
    return {"grilles": [g] * (n + 1), "lots": [{"actions": [{"action": "RIGHT"}]}] * n, "precedents": []}


def test_fc2_drapeau_eteint_moteur_local(monkeypatch, tmp_path):
    _eteindre(monkeypatch)
    monkeypatch.delenv("CHRYS_MOTEUR_PROCESSUS", raising=False)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s, m = Ligne(), Factice()
    b = branche.creer(s, tmp_path, moteur=m)
    assert b.moteur is m and "moteur_processus" not in b.bilan()


def test_meme_partie_au_point_pres_dans_l_ouvrier(monkeypatch, tmp_path):
    """Même partie (plan joué sans modèle, porte 1 et 2, suivi coup par coup), moteur local puis dans l'ouvrier : trace
    (hors horodatage, cpu) et bilan identiques hors moteur_cpu_s / moteur_processus."""
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    res = []
    for drapeau in ("0", "1"):
        monkeypatch.setenv("CHRYS_MOTEUR_PROCESSUS", drapeau)
        s = Ligne()
        b = branche.creer(s, tmp_path / drapeau, moteur=Factice(plan=("RIGHT",) * 5))
        assert isinstance(b.moteur, MoteurDistant) == (drapeau == "1")
        t = _scenario(b, s, n=6)
        bl = {k: v for k, v in b.bilan().items() if k not in ("moteur_cpu_s", "moteur_processus", "coups_plan_par_niveau")}
        appels = [{k: v for k, v in json.loads(x).items() if k not in ("t", "cpu_s")}
                  for x in b.trace.read_text().splitlines() if '"appel": true' in x]
        res.append((t, bl, appels, s.niveaux, s.appels_modele))
        if drapeau == "1":
            mp = b.bilan()["moteur_processus"]
            assert mp["appels"] >= 2 and mp["demarrages"] == 1 and mp["delais"] == 0
            b.moteur.fermer()
    assert res[0] == res[1] and res[0][3] >= 1


def _debit_pendant(fn):
    """Itérations/s d'un fil « autre flux » (Python pur) seul, puis pendant fn() ; rend (rapport, seul, pendant)."""
    stop, n = threading.Event(), [0]

    def compter():
        while not stop.is_set():
            sum(range(200))
            n[0] += 1
    fil = threading.Thread(target=compter, daemon=True)
    fil.start()
    time.sleep(0.2)
    n0, t0 = n[0], time.perf_counter()
    time.sleep(1.0)
    seul = (n[0] - n0) / (time.perf_counter() - t0)
    n0, t0 = n[0], time.perf_counter()
    fn()
    pendant = (n[0] - n0) / (time.perf_counter() - t0)
    stop.set()
    fil.join()
    return pendant / seul, seul, pendant


def test_debit_autre_flux_garde_80_pour_cent(monkeypatch, capsys):
    monkeypatch.setenv("CHRYS_MOTEUR_PROCESSUS_DELAI_S", "60")
    monkeypatch.delenv("CHRYS_TEST_CPU_S", raising=False)
    local = Lent(2.0)
    r_local, s_l, p_l = _debit_pendant(lambda: local.proposer(_hist(3)))
    d = MoteurDistant(Lent(2.0))
    monkeypatch.setenv("CHRYS_TEST_CPU_S", "0")
    d.proposer(_hist(3))  # démarrage de l'ouvrier (coût spawn + imports) hors mesure
    monkeypatch.setenv("CHRYS_TEST_CPU_S", "2")
    r_dist, s_d, p_d = _debit_pendant(lambda: d.proposer(_hist(4)))
    with capsys.disabled():
        print(f"\n[débit] local : {r_local:.2f} ({p_l:.0f}/{s_l:.0f} it/s) ; ouvrier : {r_dist:.2f} ({p_d:.0f}/{s_d:.0f})"
              f" ; {d.mesures_processus}")
    assert d.infos["cpu_s"] >= 2.0 and d.infos["pid"] != os.getpid()
    assert d.infos["appels"] == 2 and d.infos["n"] == {"grilles": 5, "lots": 4, "precedents": 0}  # état dans l'ouvrier
    d.fermer()
    assert r_dist >= 0.8
    assert r_local < 0.7  # sans le correctif, l'autre flux perd au moins 30 % (GIL partagé)


def test_delai_dur_resultat_tardif_jete_ouvrier_relance(monkeypatch):
    monkeypatch.setenv("CHRYS_MOTEUR_PROCESSUS_DELAI_S", "1.5")
    monkeypatch.setenv("CHRYS_TEST_DORT_S", "0")
    d = MoteurDistant(Dort())
    assert d.proposer(_hist(1)) is not None  # ouvrier démarré
    monkeypatch.setenv("CHRYS_TEST_DORT_S", "8")
    monkeypatch.setenv("CHRYS_TEST_MARQUE", "tardif")
    t0 = time.monotonic()
    assert d.proposer(_hist(2)) is None and time.monotonic() - t0 < 4
    assert "délai" in d.infos["refus"] and d.mesures_processus["delais"] == 1 and d._h["p"] is None
    monkeypatch.setenv("CHRYS_TEST_DORT_S", "0")
    monkeypatch.setenv("CHRYS_TEST_MARQUE", "neuf")
    assert d.proposer(_hist(3)) is not None and d.infos["marque"] == "neuf"  # rien du calcul tardif
    assert d.mesures_processus["demarrages"] == 2
    d.fermer()
    assert d.proposer(_hist(3)) is None and d.infos["refus"] == "ouvrier fermé"


def test_envoi_incremental(monkeypatch):
    monkeypatch.setenv("CHRYS_TEST_CPU_S", "0")
    d = MoteurDistant(Lent(0))
    h = _hist(1)
    h["grilles"] = [[[i % 16] * 64 for _ in range(64)] for i in range(40)]
    h["lots"] = h["lots"] * 39
    d.proposer(h)
    gros = d.mesures_processus["octets_envoyes"]
    h2 = {"grilles": h["grilles"] + [[[1] * 64 for _ in range(64)]], "lots": h["lots"] + h["lots"][:1], "precedents": []}
    d.proposer(h2)
    petit = d.mesures_processus["octets_envoyes"] - gros
    assert d.infos["n"] == {"grilles": 41, "lots": 40, "precedents": 0} and petit < gros / 10
    d.proposer({"grilles": h2["grilles"][:2], "lots": h2["lots"][:1], "precedents": []})  # niveau neuf : renvoi complet
    assert d.infos["n"] == {"grilles": 2, "lots": 1, "precedents": 0}
    d.fermer()


def test_moteur_c_sk01_meme_plan_qu_en_local(monkeypatch, capsys):
    pytest.importorskip("clingo")
    pytest.importorskip("arc_agi")
    from pathlib import Path

    from chrysalide.arc3.logique.jeux import segments
    from chrysalide.arc3.moteur import MoteurC
    synth = Path("experiments/T2.8/synth_envs")
    if not (synth / "solutions.json").exists():
        pytest.skip("jeux synthétiques absents")
    monkeypatch.setenv("CHRYS_MOTEUR_PROCESSUS_DELAI_S", "120")
    gid, sols = "sk01-38abff94", json.loads((synth / "solutions.json").read_text())
    s0, s1 = segments(gid, synth, sols[gid][0] + sols[gid][1][:1])[:2]

    def lots(acts):
        return [{"actions": [{"action": NOMS[a]}]} for a in acts]
    h = {"grilles": s1["grilles"], "lots": lots(s1["actions"]),
         "precedents": [{"grilles": s0["grilles"], "lots": lots(s0["actions"]), "finale": lots([s0["finale"]])[0]}]}
    loc = MoteurC(budget=30)
    r_loc = loc.proposer(h)
    d = MoteurDistant(MoteurC(budget=30))
    t0 = time.perf_counter()
    r_d = d.proposer(h)
    t_d = time.perf_counter() - t0
    assert r_loc is not None and r_d == r_loc
    t0 = time.perf_counter()
    ok_d = porte(d, r_d[1], h["grilles"], h["lots"])  # porte jugée dans le parent, sur la perception allégée
    t_porte = time.perf_counter() - t0
    ok_l = porte(loc, r_loc[1], h["grilles"], h["lots"])
    assert ok_d is not None and ok_l is not None and d.tr.etats == [] and d.tr.s == loc.tr.s
    assert d.classes_inconnues(h["precedents"], h["grilles"][0]) == loc.classes_inconnues(h["precedents"], h["grilles"][0])
    with capsys.disabled():
        print(f"\n[sk01] cpu local {loc.infos['cpu_s']} s, ouvrier {d.infos['cpu_s']} s, mur ouvrier (spawn compris) "
              f"{t_d:.2f} s, porte parent {t_porte * 1000:.1f} ms, {len(h['grilles'])} images ; {d.mesures_processus}")
    d.fermer()
