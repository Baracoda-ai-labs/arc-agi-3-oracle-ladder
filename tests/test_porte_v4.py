"""D (CW-463/464) : porte v4 dans le harnais de Franzen — VRAIE garde, VRAIE branche, VRAI jeu (faux solveur adossé à
arc_agi hors ligne) et vraie v4 du paquet v2. Contrôles : g50t, la v4 gagne ses niveaux puis rend la main ; éteint = rien."""
import json
import types
from pathlib import Path

import pytest

from chrysalide.arc3 import branche, garde

RACINE = Path(__file__).resolve().parents[1]
PAQUET = RACINE / "experiments/GEL27_moteur_seul_v2"
CODES = {"RESET": 0, "UP": 1, "DOWN": 2, "LEFT": 3, "RIGHT": 4, "SPACE": 5, "UNDO": 7}


class SolveurReel:
    """Ce que la garde voit d'un solveur de Franzen, adossé au vrai jeu hors ligne."""

    def __init__(self, jeu):
        from chrysalide.arc3.logique.jeux import environnement, jouer_action
        self.env, self._jouer = environnement(jeu, RACINE / "experiments/arc3/environment_files"), jouer_action
        self.f = self.env.reset()
        self.niv = 0
        self.game = types.SimpleNamespace(game_run=types.SimpleNamespace(game_id=jeu))

    def current_frame(self):
        return types.SimpleNamespace(grid=[list(map(int, r)) for r in self.f.frame[-1]],
                                     available_actions=list(self.f.available_actions or []))

    def step_env(self, arguments):
        a = arguments["actions"][0]
        n = str(a["action"]).upper()
        self.f = self._jouer(self.env, ("clic", int(a["col"]), int(a["row"])) if n == "MOUSE" else CODES[n])
        fini = self.f.levels_completed > self.niv
        self.niv = self.f.levels_completed
        st = str(self.f.state)
        return {"executed": True, "level_completed": fini, "game_over": "GAME_OVER" in st, "state": st,
                "run_complete": "WIN" in st}


@pytest.fixture
def propre(monkeypatch, tmp_path):
    for n in branche.INTERRUPTEURS:
        monkeypatch.delenv(f"CHRYS_{n}", raising=False)
    monkeypatch.setenv("CHRYS_DOSSIER", str(tmp_path))
    monkeypatch.setenv("CHRYS_GARDE_MUR_S", "3600")
    monkeypatch.setenv("CHRYS_PORTE_V4_PAQUET", str(PAQUET))
    return tmp_path


def _trace(d):
    return [json.loads(x) for f in Path(d).glob("*_trace.jsonl") for x in f.read_text().splitlines()]


def test_eteint_rien(propre):
    s = SolveurReel("g50t")
    assert garde.creer(s, propre) is None  # aucun interrupteur : Franzen seul, solveur intact


def test_g50t_la_v4_joue_puis_rend_la_main(propre, monkeypatch):
    pytest.importorskip("arc_agi")
    if not (PAQUET / "livraison_p1/code/agent_p1/jouer.py").exists():
        pytest.skip("paquet v2 absent")
    monkeypatch.setenv("CHRYS_PORTE_V4", "1")
    s = SolveurReel("g50t")
    g = garde.creer(s, propre)
    assert g is not None and g.tour() is True          # 1er tour : la v4 a joué
    assert g.tour() is False                           # ensuite : Franzen (plus de porte)
    lignes = [x for x in _trace(propre) if x.get("source") == "porte_v4"]
    fin = next(x["fin"] for x in lignes if "fin" in x)
    assert fin["niveaux"] >= 5, lignes                 # F : 7 niveaux par la v4 sur g50t (v2)
    assert s.niv == fin["niveaux"]                     # les niveaux sont gagnés dans le VRAI jeu
    coups = [x for x in _trace(propre) if "lot" in x]
    assert coups and all(x["source"] == "moteur" for x in coups)  # attribution : tous les coups joués sont ceux de la v4
    assert len(coups) == fin["coups"]
    print("PORTE g50t", fin)


def test_ft09_non_reconnu_rend_la_main_aussitot(propre, monkeypatch):
    """Contrôle négatif : ft09 (clics) n'est pas une scène v4 ; la porte rend la main avec 4 coups de sonde au plus."""
    pytest.importorskip("arc_agi")
    if not (PAQUET / "livraison_p1/code/agent_p1/jouer.py").exists():
        pytest.skip("paquet v2 absent")
    monkeypatch.setenv("CHRYS_PORTE_V4", "1")
    s = SolveurReel("ft09")
    g = garde.creer(s, propre)
    g.tour()
    fin = next(x["fin"] for x in _trace(propre) if x.get("source") == "porte_v4" and "fin" in x)
    assert fin["niveaux"] == 0 and fin["coups"] <= 4, fin
    assert g.tour() is False  # Franzen joue la suite, sans nouvelle sonde



def _portes_ensemble(propre, monkeypatch, verrou=True):
    """5 vrais jeux, une garde chacun, départ ensemble dans des fils ; → (fins des portes, solveurs, modules avant, après)."""
    import contextlib
    import sys
    import threading
    from chrysalide.arc3 import porte_v4
    pytest.importorskip("arc_agi")
    if not (PAQUET / "livraison_p1/code/agent_p1/jouer.py").exists():
        pytest.skip("paquet v2 absent")
    monkeypatch.setenv("CHRYS_PORTE_V4", "1")
    if not verrou:
        monkeypatch.setattr(porte_v4, "_VERROU", contextlib.nullcontext())
    jeux = ["g50t", "ka59", "ft09", "ls20", "cd82"]
    solveurs = {j: SolveurReel(j) for j in jeux}
    gardes = {j: garde.creer(solveurs[j], propre) for j in jeux}
    avant = {k: v for k, v in sys.modules.items() if k == "chrysalide" or k.startswith("chrysalide.")}
    depart = threading.Barrier(len(jeux))
    erreurs = []

    def un(j):
        try:
            depart.wait()
            gardes[j].tour()
        except Exception as e:  # noqa: BLE001
            erreurs.append((j, repr(e)))

    fils = [threading.Thread(target=un, args=(j,)) for j in jeux]
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    apres = {k: v for k, v in sys.modules.items() if k == "chrysalide" or k.startswith("chrysalide.")}
    assert not erreurs, erreurs  # la garde n'élève jamais, même sans verrou
    fins = [x["fin"] for x in _trace(propre) if x.get("source") == "porte_v4" and "fin" in x]
    return fins, solveurs, avant, apres


def test_portes_simultanees_dans_des_fils(propre, monkeypatch):
    """A (24/10, P1 au pod) : les 10 jeux de Franzen sont des fils d'un même processus. Plusieurs portes ouvertes ensemble
    ne doivent ni s'effacer leurs modules (KeyError 'chrysalide.arc3' au pod), ni perdre g50t, ni laisser `sys.modules`
    différent après coup (CCM-327-B : mêmes clés, mêmes objets pour `chrysalide*`)."""
    fins, solveurs, avant, apres = _portes_ensemble(propre, monkeypatch)
    assert len(fins) == 5, fins
    assert not [f for f in fins if str(f.get("raison", "")).startswith("erreur")], fins
    assert solveurs["g50t"].niv >= 5, fins                    # g50t gagné par la v4 même avec 4 autres portes ouvertes
    perdus = [k for k in avant if apres.get(k) is not avant[k]]
    nouveaux = {k: getattr(apres[k], "__file__", "") or "" for k in apres.keys() - avant.keys()}
    assert not perdus, perdus                                # tout module d'avant est rétabli, même objet
    assert not [k for k, f in nouveaux.items() if str(PAQUET) in f], nouveaux  # aucun module du paquet ne reste


def test_sans_verrou_les_portes_se_marchent_dessus(propre, monkeypatch):
    """Contrôle F-C2 du verrou (CCM-328-B) : SANS lui, les portes simultanées s'effacent leurs modules et le comportement
    correct casse — selon l'ordonnancement, KeyError 'chrysalide…' (P1 au pod) ou portes muettes et g50t perdu (0 coup).
    Un changement qui rendrait le verrou inopérant se voit ici : on exige que le critère du test positif ÉCHOUE."""
    fins, solveurs, _, _ = _portes_ensemble(propre, monkeypatch, verrou=False)
    erreur = [f for f in fins if str(f.get("raison", "")).startswith("erreur")]
    assert erreur or solveurs["g50t"].niv < 5, fins
