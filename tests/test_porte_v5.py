"""Porte v5 : vrai jeu local, vraie garde, vraie branche, vraie v4 dans un vrai enfant (contrat E_PORTE5)."""
import json
import threading
import time
from pathlib import Path

import pytest
from test_porte_v4 import PAQUET, SolveurReel

from chrysalide.arc3 import branche, garde, porte_v5


@pytest.fixture
def propre(monkeypatch, tmp_path):
    for n in branche.INTERRUPTEURS:
        monkeypatch.delenv(f"CHRYS_{n}", raising=False)
    monkeypatch.delenv("CHRYS_STAGNATION_COUPS", raising=False)
    monkeypatch.setenv("CHRYS_DOSSIER", str(tmp_path))
    monkeypatch.setenv("CHRYS_GARDE_MUR_S", "3600")
    monkeypatch.setenv("CHRYS_PORTE_V4_PAQUET", str(PAQUET))
    return tmp_path


def _allume(monkeypatch):
    pytest.importorskip("arc_agi")
    monkeypatch.setenv("CHRYS_PORTE5", "1")


def _lignes(d):
    return [json.loads(x) for f in Path(d).glob("*_trace.jsonl") for x in f.read_text().splitlines()]


def _fins(d):
    return [x["fin"] for x in _lignes(d) if x.get("source") == "porte_v5" and "fin" in x]


def test_eteint_rien(propre):
    assert garde.creer(SolveurReel("g50t"), propre) is None


@pytest.mark.parametrize("jeu,mini", [("g50t", 7), ("ka59", 5)])
def test_gains_variante_empirique(propre, monkeypatch, jeu, mini):
    _allume(monkeypatch)
    s = SolveurReel(jeu)
    g = garde.creer(s, propre)
    assert g.tour() is True
    fin = _fins(propre)[0]
    assert s.niv == fin["niveaux"] >= mini, fin
    coups = [x for x in _lignes(propre) if "lot" in x]
    assert len(coups) == fin["coups"] and all(x["source"] == "moteur" for x in coups)
    assert "RESET" not in {x["lot"]["actions"][0]["action"] for x in coups}
    assert g.tour() is False  # une seule ouverture de départ, pas de stagnation demandée


def test_re86_sort_par_repetition(propre, monkeypatch):
    _allume(monkeypatch)
    s = SolveurReel("re86")
    g = garde.creer(s, propre)
    g.tour()
    fin = _fins(propre)[0]
    assert fin["raison"] == "repetition sans progres" and fin["coups"] < 99 and s.niv == 0, fin


@pytest.mark.parametrize("jeu,niveaux,raison", [("g50t", 3, "sondes epuisees"), ("ka59", 1, "ecart non reexplique")])
def test_strict_coupe(propre, monkeypatch, jeu, niveaux, raison):
    _allume(monkeypatch)
    monkeypatch.setenv("CHRYS_PORTE5_STRICT", "1")
    s = SolveurReel(jeu)
    garde.creer(s, propre).tour()
    fin = _fins(propre)[0]
    assert s.niv == niveaux and fin["raison"] == raison, fin


def test_ft09_non_reconnu_rend_la_main(propre, monkeypatch):
    _allume(monkeypatch)
    s = SolveurReel("ft09")
    g = garde.creer(s, propre)
    g.tour()
    fin = _fins(propre)[0]
    assert fin["niveaux"] == 0 and fin["coups"] <= 4, fin
    assert g.tour() is False


def test_deux_parties_simultanees_memes_jeux(propre, monkeypatch):
    """Sans verrou : deux g50t et un ka59 ensemble, aucune contamination, sys.modules du parent intact."""
    import sys
    _allume(monkeypatch)
    avant = {k for k in sys.modules if k.startswith(("agent_p1", "boucle_v4"))}
    solveurs = [SolveurReel(j) for j in ("g50t", "g50t", "ka59")]
    gardes = [garde.creer(s, propre) for s in solveurs]
    fils = [threading.Thread(target=g.tour) for g in gardes]
    [f.start() for f in fils]
    [f.join() for f in fils]
    assert [s.niv for s in solveurs] == [7, 7, 5]
    assert {k for k in sys.modules if k.startswith(("agent_p1", "boucle_v4"))} == avant


def test_prise_tardive_compteur_reel(propre, monkeypatch):
    """Défaut v4 : niveaux=0 en reprise tardive ferait croire à une victoire au 1er coup."""
    _allume(monkeypatch)
    monkeypatch.setenv("CHRYS_STAGNATION_COUPS", "3")
    s = SolveurReel("ka59")
    g = garde.creer(s, propre)
    p = porte_v5.Porte5(g.b)
    p.depart_fait = True
    g.b.moniteur.niveau, g.b.moniteur.actions_niveau = 2, 5  # le jeu réel n'a pas ce compte : seul le parent fait foi
    assert p._etat()["niveaux"] == 2
    p.tour()
    assert all(not x.get("victoire") or s.niv > 0 for x in _lignes(propre) if x.get("source") == "porte_v5")
    assert 2 in p.niveaux_tentes
    n = len(_fins(propre))
    p.tour()
    assert len(_fins(propre)) == n  # une tentative par niveau



@pytest.mark.parametrize("corps,raison", [
    ("import sys;sys.stdin.readline();print('{\"t\":\"action\",\"n\":1,\"sha\":\"perime\",\"action\":{\"action\":\"UP\"}}',flush=True);sys.stdin.readline()", "proposition refusee"),
    ("import sys;sys.stdin.readline();sys.exit(1)", "enfant mort"),
    ("import sys,time;sys.stdin.readline();time.sleep(30)", "delai"),
    ("import sys;sys.stdin.readline();print('pas du json',flush=True);sys.stdin.readline()", "reponse illisible"),
])
def test_enfant_defaillant_aucun_coup(propre, monkeypatch, tmp_path, corps, raison):
    _allume(monkeypatch)
    monkeypatch.setenv("CHRYS_PORTE5_ATTENTE_S", "2")
    faux = tmp_path / "faux.py"
    faux.write_text(corps)
    monkeypatch.setattr(porte_v5, "ENFANT", faux)
    s = SolveurReel("g50t")
    g = garde.creer(s, propre)
    avant = [list(r) for r in s.current_frame().grid]
    assert g.tour() is False
    fin = _fins(propre)[0]
    assert fin["raison"] == raison and fin["coups"] == 0, fin
    assert s.current_frame().grid == avant


def test_prise_tardive_reelle_apres_coups_du_modele(propre, monkeypatch):
    """Vraie reprise : 5 coups joués par « Franzen » sur le vrai jeu, puis stagnation. Compteur réel, attribution exacte."""
    _allume(monkeypatch)
    monkeypatch.setenv("CHRYS_STAGNATION_COUPS", "5")
    s = SolveurReel("ka59")
    g = garde.creer(s, propre)
    g.p5 = porte_v5.Porte5(g.b)
    g.p5.depart_fait = True
    assert g.tour() is False  # sous le seuil
    for a in ("UP", "LEFT", "DOWN", "RIGHT", "UP"):
        s.step_env({"actions": [{"action": a}]})
    g.tour()
    assert g.b.moniteur.niveau == s.niv  # compteur du parent = jeu réel, aucun niveau fantôme
    lignes = _lignes(propre)
    assert [x["source"] for x in lignes if "lot" in x][:5] == ["modele"] * 5
    fin = _fins(propre)[0]
    assert fin["motif"] == "stagnation" and s.niv == fin["niveaux"], fin
    print("TARDIVE", fin)


def test_dix_parties_simultanees(propre, monkeypatch):
    """10 flux comme au pod : aucune erreur, chaque enfant termine, g50t et ka59 gardent leurs niveaux."""
    _allume(monkeypatch)
    jeux = ["ar25", "bp35", "cd82", "dc22", "ft09", "g50t", "ka59", "lf52", "lp85", "ls20"]
    solveurs = {j: SolveurReel(j) for j in jeux}
    gardes = [garde.creer(solveurs[j], propre) for j in jeux]
    fils = [threading.Thread(target=g.tour) for g in gardes]
    [f.start() for f in fils]
    [f.join() for f in fils]
    fins = _fins(propre)
    assert len(fins) == 10 and not [f for f in fins if str(f["raison"]).startswith(("enfant", "reponse", "paquet", "protocole"))], fins
    assert (solveurs["g50t"].niv, solveurs["ka59"].niv) == (7, 5)
    print("DIX", [(f["niveaux"], f["coups"], f["raison"], f["secondes"]) for f in fins])


def _faux_enfant(monkeypatch, tmp_path, corps):
    monkeypatch.setenv("CHRYS_PORTE5_ATTENTE_S", "5")
    faux = tmp_path / "faux.py"
    faux.write_text("import hashlib,json,sys\ne=json.loads(sys.stdin.readline())\n"
                    "sha=hashlib.sha256(json.dumps(e['grille'],separators=(',',':')).encode()).hexdigest()[:16]\n"
                    "act=dict(t='action',n=1,sha=sha,action={'action':'UP'},niveau=e['niveaux'],obs=e['obs'])\n" + corps)
    monkeypatch.setattr(porte_v5, "ENFANT", faux)


def test_action_tamponnee_apres_echeance_refusee(propre, monkeypatch, tmp_path):
    """Vraie suite tamponnée (niveau + action dans la même écriture) : l'échéance passe pendant le traitement du niveau."""
    _allume(monkeypatch)
    monkeypatch.setenv("CHRYS_PORTE5_MUR_S", "0.5")
    _faux_enfant(monkeypatch, tmp_path, "print(json.dumps(dict(t='niveau'))+chr(10)+json.dumps(act),flush=True);sys.stdin.readline()")
    s = SolveurReel("g50t")
    g = garde.creer(s, propre)
    noter = g.b._noter

    def lent(x):
        if x.get("t") == "niveau":
            time.sleep(0.8)
        noter(x)
    g.b._noter = lent
    assert g.tour() is False
    fin = _fins(propre)[0]
    assert fin["raison"] == "delai" and fin["coups"] == 0, fin


@pytest.mark.parametrize("change", ["act['niveau']+=1", "act['obs']+=1", "act['sha']='0'", "act.pop('niveau')"])
def test_meme_image_autre_identite_refusee(propre, monkeypatch, tmp_path, change):
    _allume(monkeypatch)
    _faux_enfant(monkeypatch, tmp_path, change + ";print(json.dumps(act),flush=True);sys.stdin.readline()")
    s = SolveurReel("g50t")
    g = garde.creer(s, propre)
    assert g.tour() is False
    fin = _fins(propre)[0]
    assert fin["raison"] == "proposition refusee" and fin["coups"] == 0, fin


def test_budget_sonde_du_parent(propre, monkeypatch, tmp_path):
    """Le parent compte lui-même : un enfant qui ignore le budget ne joue pas de sonde de plus, et une reprise ne réarme rien."""
    _allume(monkeypatch)
    monkeypatch.setenv("CHRYS_PORTE5_STRICT", "1")
    _faux_enfant(monkeypatch, tmp_path, "act['sonde']=True;print(json.dumps(act),flush=True);sys.stdin.readline()")
    s = SolveurReel("g50t")
    g = garde.creer(s, propre)
    g.p5 = porte_v5.Porte5(g.b)
    g.p5.sondes = 4
    assert g.tour() is False
    fin = _fins(propre)[0]
    assert fin["raison"] == "sondes epuisees" and fin["coups"] == 0, fin


def test_etat_terminal_refuse(propre, monkeypatch):
    _allume(monkeypatch)
    s = SolveurReel("g50t")
    g = garde.creer(s, propre)
    p = porte_v5.Porte5(g.b)
    e = p._etat()
    m = {"action": {"action": "UP"}, "niveau": e["niveaux"], "obs": e["obs"], "sha": porte_v5.empreinte(e["grille"])}
    assert p._refus(m, e, e["grille"], time.monotonic()) is None
    vraie = s.current_frame()

    class Fin:
        state, available_actions = "GAME_OVER", getattr(vraie, "available_actions", None)
    s.current_frame = lambda: Fin
    assert p._refus(m, e, e["grille"], time.monotonic()) == "etat terminal"


class _Canal:
    def __init__(self):
        self.dits = []

    def dire(self, **m):
        self.dits.append(m)


class _Modele:
    def __init__(self):
        self.lois = {}


def step(modele, s, a):  # porte le nom attendu par le comparateur
    return modele.lois.get((s, a), s + a)


def _suivi(prefixe, ecart):
    from chrysalide.arc3 import porte_v5_enfant as E
    su, mod = E.Suivi(_Canal()), _Modele()
    mod._p5_prefixe = prefixe
    su.ecart = (mod, step, *ecart)
    return su, E


def test_reparation_du_prefixe_autorisee():
    su, _ = _suivi([(0, 1, 1), (1, 1, 2), (2, 1, 2)], (2, 1, 3, 2))  # bloqué en 2 : rien d'autre à réexpliquer
    su.controler()
    assert su.reparations == 1 and su.ecart is None and su.canal.dits[-1]["repare"] is True


def test_recalage_seul_refuse():
    su, E = _suivi([(0, 1, 1), (1, 1, 5)], (1, 1, 2, 5))  # copier l'observation (5) n'explique rien
    with pytest.raises(E.Arret):
        su.controler()
    assert su.reparations == 0


def test_correction_du_seul_dernier_coup_refusee():
    su, E = _suivi([(2, 1, 3), (0, 1, 1), (2, 1, 2)], (2, 1, 3, 2))  # le même (état, coup) avait bougé plus tôt
    with pytest.raises(E.Arret):
        su.controler()
    assert su.reparations == 0


def test_inventeur_sans_accord_arrete():
    from chrysalide.arc3 import porte_v5_enfant as E
    su = E.Suivi(_Canal())
    su.accords = [True, False]
    su.controler()
    su.accords = [False, False]
    with pytest.raises(E.Arret):
        su.controler()


def test_historique_fidele_une_seule_restitution(propre, monkeypatch):
    _allume(monkeypatch)
    monkeypatch.setenv("CHRYS_HISTORIQUE_FIDELE", "1")

    class Analyseur:
        def __init__(self):
            self.appels = []

        def _summarize_step_sequence(self, charges):
            self.appels.append(list(charges))
            return "resume"
    s = SolveurReel("g50t")
    s.analyzer = Analyseur()
    g = garde.creer(s, propre)
    g.tour()
    fin = _fins(propre)[0]
    assert fin["coups"] > 0 and len(s.analyzer.appels) == 1 and len(s.analyzer.appels[0]) == fin["coups"]
    assert s.analyzer._last_step_summary == "resume" and g.b.payloads_auto == []
    g.tour()
    assert len(s.analyzer.appels) == 1  # aucune restitution en double


def test_resume_survit_a_la_mise_en_route(propre, monkeypatch):
    """Comme ToolAgent._ensure_session au 1er tour : la mise en route remet le résumé à None."""
    _allume(monkeypatch)
    monkeypatch.setenv("CHRYS_HISTORIQUE_FIDELE", "1")

    class Analyseur:
        _last_step_summary = None

        def _summarize_step_sequence(self, charges):
            return {"n": len(charges)}

        def _ensure_session(self, chemin):
            self._last_step_summary = None
    s = SolveurReel("g50t")
    s.analyzer = Analyseur()
    g = garde.creer(s, propre)
    g.tour()
    n = _fins(propre)[0]["coups"]
    s.analyzer._ensure_session("x")
    assert s.analyzer._last_step_summary == {"n": n}
    s.analyzer._ensure_session("x")  # une seule fois
    assert s.analyzer._last_step_summary is None
