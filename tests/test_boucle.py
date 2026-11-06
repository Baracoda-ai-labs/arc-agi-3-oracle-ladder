# SPDX-License-Identifier: MIT-0
"""V1 de CW-162/163 (CHRYS_BOUCLE) : diagnostic à étages puis boucle avant de rendre la main au modèle.
F-C2 (éteint = V0 au point près), réussite sans LLM, budget épuisé → LLM, test « inconnu » qui ne bloque pas."""
import json

from chrysalide.arc3 import branche, diagnostic
from chrysalide.arc3.moteur import MoteurFormel
from tests.test_moteur import Factice, Ligne, _droite, _eteindre, _sans_moteur, _scenario

BOUCLE = ("blocages", "boucles_tentees", "boucles_reussies", "boucle_cpu_s", "boucle_coups", "diagnostics")


class Suite(MoteurFormel):
    """Moteur factice : rend successivement les plans de `plans` (le dernier se répète) ; note budget et option etage."""
    def __init__(self, *plans):
        self.plans, self.appels, self.infos, self.budget, self.vus = list(plans), 0, {}, 1.0, []

    def proposer(self, historique, etage=None):
        self.vus.append((self.budget, etage))
        p = self.plans[min(self.appels, len(self.plans) - 1)]
        self.appels += 1
        self.infos = {"cpu_s": 0.001}
        return [{"action": a} for a in p], _droite(1)


def _allumer(monkeypatch, **env):
    _eteindre(monkeypatch)
    for n in ("BOUCLE", "BOUCLE_TOURS", "BOUCLE_CPU_S", "BOUCLE_COUPS", "TUTO"):
        monkeypatch.delenv(f"CHRYS_{n}", raising=False)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    for k, v in env.items():
        monkeypatch.setenv(f"CHRYS_{k}", v)


def _lignes(b, source="boucle"):
    return [json.loads(x) for x in b.trace.read_text().splitlines() if f'"source": "{source}"' in x]


def test_fc2_boucle_eteinte_ou_sans_blocage_inchange(monkeypatch, tmp_path):
    # éteinte : sur un blocage sans_but, la main revient au modèle tout de suite (V0), aucune clé ni ligne de boucle
    _allumer(monkeypatch)
    s, m = Ligne(), Suite(("RIGHT",), ("RIGHT", "RIGHT"))
    b = branche.creer(s, tmp_path / "v0", moteur=m)
    s.jouer_modele()
    assert not b.tour() and b.raison == "sans_but" and m.appels == 1 and b.bc_m is None
    assert not any(k in b.bilan() for k in BOUCLE) and '"source": "boucle"' not in b.trace.read_text()
    # allumée sans CHRYS_MOTEUR : aucun effet (la branche n'existe même pas)
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_BOUCLE", "1")
    assert branche.creer(Ligne(), tmp_path / "seule") is None
    # allumée, moteur muet (aucun blocage : debut_jeu / filet) : coups, trace et bilan identiques hors nouvelles clés
    _allumer(monkeypatch)
    s1, m1 = Ligne(), Factice(rien=True)
    b1 = branche.creer(s1, tmp_path / "off", moteur=m1)
    t_off = _scenario(b1, s1, n=8)
    monkeypatch.setenv("CHRYS_BOUCLE", "1")
    s2, m2 = Ligne(), Factice(rien=True)
    b2 = branche.creer(s2, tmp_path / "on", moteur=m2)
    assert _scenario(b2, s2, n=8) == t_off and s2.appels_modele == s1.appels_modele and m2.appels == m1.appels
    bl = b2.bilan()
    assert all(n.pop("mode") == "rapide" for n in bl["coups_plan_par_niveau"])  # CW-169 : seule clé ajoutée par niveau
    assert {k: v for k, v in bl.items() if k not in BOUCLE} == b1.bilan()
    assert _sans_moteur(b1.bilan()) == _sans_moteur({k: v for k, v in bl.items() if k not in BOUCLE})
    assert (bl["blocages"], bl["boucles_tentees"], bl["boucle_coups"]) == (0, 0, 0)


def test_blocage_etage_3_replan_le_moteur_reprend_sans_llm(monkeypatch, tmp_path):
    """(i) plan non gagnant (porte 2 refusée) → diagnostic étage 3 (étage 0 inconnu, 1 et 2 sains) → réappel à budget
    doublé, option etage=3 → plan gagnant → joué sans modèle, niveau réussi."""
    _allumer(monkeypatch, BOUCLE="1")
    s, m = Ligne(), Suite(("RIGHT",), ("RIGHT", "RIGHT"))
    b = branche.creer(s, tmp_path, moteur=m)
    s.jouer_modele()
    assert b.tour() and b.bc is None and m.appels == 2 and m.vus[1] == (2.0, 3) and m.budget == 1.0
    assert b.tour() and s.niveaux == 1 and s.appels_modele == 1  # 2e coup du plan, sans modèle
    bl = b.bilan()
    assert (bl["blocages"], bl["boucles_tentees"], bl["boucles_reussies"], bl["boucle_coups"]) == (1, 1, 1, 0)
    assert bl["diagnostics"] == {"par_etage": {"3": 1}, "par_test": {"3:porte2_refusee": 1}}
    assert bl["declencheurs"]["sans_but"] == 0 and bl["moteur_plans_gagnants_reels"] == 1
    d = [x for x in _lignes(b) if x.get("diagnostic")]
    assert len(d) == 1 and d[0]["etage"] == 3 and d[0]["action"] == "reproposer"
    assert d[0]["resultats"][:3] == ["0:echelle_blocs=inconnu", "1:relecture_pixel=sain", "2:porte1_refusee=sain"]
    assert _lignes(b)[-1]["fin"] == "plan" and _lignes(b)[-1]["reussie"] is True


def test_budget_epuise_main_au_llm(monkeypatch, tmp_path):
    """(ii) le moteur ne rend jamais de plan gagnant : 2 tours (CHRYS_BOUCLE_TOURS=2) puis main au modèle (sans_but) ;
    ce (niveau, raison) n'ouvre plus de boucle ; budget CPU nul → aucun tour."""
    _allumer(monkeypatch, BOUCLE="1", BOUCLE_TOURS="2")
    s, m = Ligne(), Suite(("RIGHT",))
    b = branche.creer(s, tmp_path, moteur=m)
    s.jouer_modele()
    assert not b.tour() and b.raison == "sans_but" and m.appels == 3 and b.bc is None
    bl = b.bilan()
    assert (bl["blocages"], bl["boucles_tentees"], bl["boucles_reussies"]) == (1, 1, 0)
    assert bl["diagnostics"]["par_etage"] == {"3": 2} and _lignes(b)[-1]["fin"] == "budget tours"
    s.step_env({"actions": [{"action": "UP"}]})  # coup du modèle sans effet : nouvelle transition, même blocage
    # au même niveau : compté, pas de nouvelle boucle
    assert not b.tour() and m.appels == 4 and b.bilan()["blocages"] == 2 and b.bilan()["boucles_tentees"] == 1
    _allumer(monkeypatch, BOUCLE="1", BOUCLE_CPU_S="0")
    s2, m2 = Ligne(), Suite(("RIGHT",))
    b2 = branche.creer(s2, tmp_path / "cpu", moteur=m2)
    s2.jouer_modele()
    assert not b2.tour() and m2.appels == 1 and _lignes(b2)[-1]["fin"] == "budget cpu"


def test_coups_d_experience_bornes_et_action_enregistree(monkeypatch, tmp_path):
    """Point d'extension : une action d'étage 3 enregistrée (C, B) rend des coups d'expérience ; joués sans modèle (source
    « boucle »), bornés par CHRYS_BOUCLE_COUPS, puis main au modèle."""
    _allumer(monkeypatch, BOUCLE="1", BOUCLE_COUPS="2")
    monkeypatch.setitem(diagnostic.ACTIONS, 3, list(diagnostic.ACTIONS[3]))
    diagnostic.enregistrer_action(3, "discriminant", lambda c: {"experience": [{"action": "UP"}] * 5})
    s, m = Ligne(), Suite(("RIGHT",))
    b = branche.creer(s, tmp_path, moteur=m)
    s.jouer_modele()
    assert b.tour() and b.tour() and not b.tour() and s.appels_modele == 1
    bl = b.bilan()
    assert bl["boucle_coups"] == 2 and bl["boucles_reussies"] == 0 and _lignes(b)[-1]["fin"] == "budget coups"
    assert sum("lot" in x for x in _lignes(b)) == 2


def test_test_inconnu_ne_bloque_pas(monkeypatch, tmp_path):
    """(iii) un test qui plante ou ne conclut pas rend « inconnu » : le diagnostic passe à l'étage suivant."""
    def plante(ctx):
        raise RuntimeError("perception non exposée")
    tests = {0: [("rien", lambda c: diagnostic.INCONNU)], 1: [("plante", plante), ("bizarre", lambda c: 42)],
             2: [("faute", lambda c: (diagnostic.FAUTE, {"objet": 7}))], 3: [("jamais", lambda c: diagnostic.FAUTE)]}
    e, t, d = diagnostic.diagnostic({}, tests)
    assert (e, t, d["objet"]) == (2, "faute", 7)
    assert [x["statut"] for x in d["resultats"]] == ["inconnu", "inconnu", "inconnu", "faute"]
    assert diagnostic.diagnostic({}, {0: [("s", lambda c: diagnostic.SAIN)]})[:2] == (None, None)
    # dans la branche : test d'étage 1 enregistré qui plante → toujours diagnostic étage 3, boucle réussie
    _allumer(monkeypatch, BOUCLE="1")
    monkeypatch.setitem(diagnostic.TESTS, 1, [("plante", plante), *diagnostic.TESTS[1]])
    s, m = Ligne(), Suite(("RIGHT",), ("RIGHT", "RIGHT"))
    b = branche.creer(s, tmp_path, moteur=m)
    s.jouer_modele()
    assert b.tour() and b.bilan()["boucles_reussies"] == 1 and b.bilan()["diagnostics"]["par_etage"] == {"3": 1}


def test_tests_par_defaut_sans_oracle():
    from types import SimpleNamespace
    g = [[0] * 64 for _ in range(64)]
    g[10][10] = 3
    m = MoteurFormel()
    assert diagnostic.relecture_pixel({"moteur": m, "grilles": [g]})[0] == diagnostic.SAIN
    m.rendu = lambda sc: [[0] * 64 for _ in range(64)]  # perception qui perd le joueur : relecture fausse
    assert diagnostic.relecture_pixel({"moteur": m, "grilles": [g]})[0] == diagnostic.FAUTE
    m.tr = SimpleNamespace(s=2, ox=0, oy=0, taille=(32, 32), exclues=())  # case de 2 px, objet d'un pixel : échelle fausse
    assert diagnostic.echelle_blocs({"moteur": m, "grilles": [g]})[0] == diagnostic.FAUTE
    m.tr.s, m.tr.taille = 1, (64, 64)
    assert diagnostic.echelle_blocs({"moteur": m, "grilles": [g]})[0] == diagnostic.SAIN
    assert diagnostic.classes_inconnues({"precedents": [1], "inconnues": {8}})[0] == diagnostic.FAUTE
    assert diagnostic.classes_inconnues({"precedents": []}) == diagnostic.INCONNU
    assert diagnostic.sans_plan({"dernier": {"r_none": True}, "infos": {"refus": "budget dépassé"}})[0] == diagnostic.FAUTE
