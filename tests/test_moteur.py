# SPDX-License-Identifier: MIT-0
"""P2 de CW-126 : point d'entrée du moteur formel (CHRYS_MOTEUR) dans le solveur factice de test_branche.
Contrôle F-C2 (drapeau éteint = harnais inchangé), plan joué sans modèle derrière la porte de rejeu exact, divergence →
main au modèle, refus de la porte, et la chaîne de C (perception → induction → export → plan) sans oracle."""
import json
from types import SimpleNamespace

import pytest

from chrysalide.arc3 import branche
from chrysalide.arc3.moteur import NOMS, MoteurFormel, porte


def _droite(dx):
    """Programme du langage : RIGHT déplace la couleur 3 de dx ; joueur en x = 13 → niveau suivant."""
    return {"etat": {}, "regles": [
        {"nom": "droite", "quand": ["=", ["action"], "RIGHT"], "puis": "continuer",
         "alors": [["pour", "$o", ["objets", {"couleur": 3}], [["deplacer", "$o", dx, 0]]]]},
        {"nom": "but", "quand": ["existe", "$o", ["objets", {"couleur": 3}], ["=", ["x", "$o"], 13]],
         "alors": [["niveau_suivant"]]}]}


class Ligne:
    """Jeu jouet : RIGHT avance le joueur (couleur 3) de `pas` ; à la 3e case, niveau réussi, le niveau rejoue identique."""
    def __init__(self, pas=1):
        self.n, self.pas, self.appels_modele, self.niveaux = 0, pas, 0, 0
        self._dessiner()

    def _dessiner(self):
        self.g = [[0] * 64 for _ in range(64)]
        self.g[10][10 + self.n] = 3

    def current_frame(self):
        return SimpleNamespace(grid=self.g)

    def step_env(self, arguments):
        fin = False
        for a in arguments["actions"]:
            if a["action"] == "RIGHT":
                self.n += self.pas
                if self.n >= 3:
                    fin, self.n, self.niveaux = True, 0, self.niveaux + 1
        self._dessiner()
        return {"executed": True, "level_completed": fin, "game_over": False}

    def jouer_modele(self):
        self.appels_modele += 1
        self.step_env({"actions": [{"action": "RIGHT"}]})


class Factice(MoteurFormel):
    """Moteur imposé : plan et programme fixés ; compte ses appels."""
    def __init__(self, plan=("RIGHT", "RIGHT"), prog=None, rien=False):
        self.plan, self.prog, self.rien, self.appels, self.infos = list(plan), prog or _droite(1), rien, 0, {}

    def proposer(self, historique):
        self.appels += 1
        self.infos = {"cpu_s": 0.01}
        return None if self.rien else ([{"action": a} for a in self.plan], self.prog)


def _eteindre(monkeypatch):
    for n in branche.INTERRUPTEURS:
        monkeypatch.delenv(f"CHRYS_{n}", raising=False)


def _scenario(b, s, n=4):
    """Le modèle joue chaque fois que la branche ne joue pas ; rend la trace sans horodatage ni appels du moteur."""
    for _ in range(n):
        if not b.tour():
            s.jouer_modele()
    lignes = [json.loads(x) for x in b.trace.read_text().splitlines()]
    return [{k: v for k, v in x.items() if k not in ("t", "declencheur")} for x in lignes if not x.get("appel")]


NOUVELLES = ("declencheurs", "part_coups_moteur", "jetons_llm_par_niveau_gagne",  # clés de bilan de CW-133
             "coups_sur_optimum", "coups_plan_par_niveau")  # et de CW-138 (porte 2, Tycho)


def _sans_moteur(bl):
    return {k: v for k, v in bl.items() if not k.startswith("moteur_") and k not in NOUVELLES}


def test_fc2_drapeau_eteint_harnais_inchange(monkeypatch, tmp_path):
    _eteindre(monkeypatch)
    s, m = Ligne(), Factice()
    orig = s.step_env
    assert branche.creer(s, tmp_path, moteur=m) is None and s.step_env == orig  # tous éteints : solveur intact
    for n in ("MONITEUR", "GRAPHE"):  # autres interrupteurs allumés, CHRYS_MOTEUR éteint : le moteur n'existe pas
        monkeypatch.setenv(f"CHRYS_{n}", "1")
    b = branche.creer(s, tmp_path / "off", moteur=m)
    t_off = _scenario(b, s)
    assert b.moteur is None and m.appels == 0 and _sans_moteur(b.bilan()) == b.bilan()
    assert '"declencheur"' not in b.trace.read_text()
    # même partie, moteur allumé mais muet (None à chaque tour) : coups et trace identiques au point près (hors clé
    # « declencheur » des lignes modèle), bilan identique hors clés moteur_ et CW-133
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s2, m2 = Ligne(), Factice(rien=True)
    b2 = branche.creer(s2, tmp_path / "on", moteur=m2)
    assert _scenario(b2, s2) == t_off and m2.appels > 0 and s2.appels_modele == s.appels_modele
    bl = b2.bilan()
    assert _sans_moteur(bl) == b.bilan()
    # Ligne : niveau 1 en 3 coups (debut_jeu), puis niveau 2 sans théorie (filet) ; moteur muet : 0 coup moteur
    assert bl["declencheurs"] == {**dict.fromkeys(branche.DECLENCHEURS, 0), "debut_jeu": 3, "filet": 1}
    assert bl["part_coups_moteur"] == 0.0 and bl["jetons_llm_par_niveau_gagne"] is None


def test_plan_joue_sans_modele(monkeypatch, tmp_path):
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s, m = Ligne(), Factice()
    b = branche.creer(s, tmp_path, moteur=m)
    assert not b.tour() and m.appels == 0  # aucune transition observée : le moteur n'est pas appelé
    s.jouer_modele()
    assert b.tour() and b.tour()  # porte passée : 2 coups du plan sans modèle, le 2e finit le niveau (prédit)
    assert s.appels_modele == 1 and s.niveaux == 1 and m.appels == 1
    bl = b.bilan()
    assert (bl["moteur_tours"], bl["moteur_coups_plan"], bl["moteur_divergences"], bl["moteur_plans"]) == (2, 2, 0, 1)
    assert bl["moteur_cpu_s"] > 0 and b.trace.read_text().count('"source": "moteur"') == 3  # 1 appel + 2 coups
    assert not b.tour() and m.appels == 1  # niveau neuf, aucune transition : la main au modèle
    # porte 2 : le plan gagne en simulation, joué jusqu'au bout, niveau réellement gagné ; pas d'optimum dans l'agent
    assert (bl["moteur_porte1_ok"], bl["moteur_porte1_refus"], bl["moteur_porte2_ok"], bl["moteur_porte2_refus"],
            bl["moteur_plans_gagnants_reels"]) == (1, 0, 1, 0, 1)
    assert bl["coups_sur_optimum"] is None
    assert bl["coups_plan_par_niveau"][0].pop("cpu_moteur_s") >= 0  # CW-174 : CPU du moteur par niveau
    assert bl["coups_plan_par_niveau"] == [{"niveau": 1, "coups": 3, "coups_plan": 2, "plan_gagnant": True}]


def test_porte2_refuse_un_plan_qui_ne_gagne_pas_en_simulation(monkeypatch, tmp_path):
    """CW-138 : théorie qui rejoue (porte 1 ok) mais plan trop court, sans victoire simulée → refusé, modèle sur sans_but."""
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s, m = Ligne(), Factice(plan=("RIGHT",))
    b = branche.creer(s, tmp_path, moteur=m)
    s.jouer_modele()
    assert not b.tour() and m.appels == 1 and b.plan is None and b.raison == "sans_but"
    bl = b.bilan()
    assert (bl["moteur_porte1_ok"], bl["moteur_porte2_ok"], bl["moteur_porte2_refus"], bl["moteur_plans"],
            bl["moteur_coups_plan"]) == (1, 0, 1, 0, 0)
    appel = [json.loads(x) for x in b.trace.read_text().splitlines() if '"appel": true' in x][-1]
    assert appel["porte"] is True and appel["porte2"] is False and appel["issue_simulee"] is None
    assert bl["declencheurs"]["sans_but"] == 1


def test_porte2_tronque_le_plan_au_coup_gagnant(monkeypatch, tmp_path):
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s, m = Ligne(), Factice(plan=("RIGHT",) * 5)  # victoire simulée au 2e coup : 3 coups de trop
    b = branche.creer(s, tmp_path, moteur=m)
    s.jouer_modele()
    assert b.tour() and len(b.plan["actions"]) == 2 and b.tour() and s.niveaux == 1 and b.plan is None
    bl = b.bilan()
    assert (bl["moteur_coups_plan"], bl["moteur_plans_gagnants_reels"]) == (2, 1)


def test_divergence_rend_la_main_au_modele(monkeypatch, tmp_path):
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s, m = Ligne(), Factice(plan=("RIGHT",) * 5)
    b = branche.creer(s, tmp_path, moteur=m)
    s.jouer_modele()
    s.pas = 2  # le jeu change de loi : le coup suivant ne sera pas celui prédit
    assert b.tour()  # le coup du plan est joué… et diverge
    assert b.bilan()["moteur_divergences"] == 1 and b.plan is None
    assert '"divergence": true' in b.trace.read_text()
    assert not b.tour() and m.appels == 1  # main au modèle ; le moteur n'est redemandé qu'après son coup
    s.jouer_modele()
    assert m.appels == 1 and b.bilan()["moteur_coups_plan"] == 1


def test_porte_refuse_une_theorie_qui_ne_rejoue_pas(monkeypatch, tmp_path):
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s, m = Ligne(), Factice(prog=_droite(2))
    b = branche.creer(s, tmp_path, moteur=m)
    s.jouer_modele()
    assert not b.tour() and m.appels == 1  # théorie fausse sur la transition observée : Franzen continue
    assert b.bilan()["moteur_refus_porte"] == 1 and b.bilan()["moteur_coups_plan"] == 0
    assert porte(m, _droite(1), [Ligne().g, [[0] * 64] * 64], [{"actions": [{"action": "RIGHT"}]}]) is None


def test_moteur_c_sans_niveau_reussi_rend_none():
    pytest.importorskip("clingo")
    from chrysalide.arc3.moteur import MoteurC
    s = Ligne()
    gs, lots = [s.g], []
    for _ in range(2):
        s.step_env({"actions": [{"action": "RIGHT"}]})
        gs.append(s.g)
        lots.append({"actions": [{"action": "RIGHT"}]})
    mc = MoteurC(budget=5)
    assert mc.proposer({"grilles": gs, "lots": lots, "precedents": []}) is None
    assert mc.infos["refus"] and mc.infos["cpu_s"] < 5
    assert mc.proposer({"grilles": gs[:1], "lots": [], "precedents": []}) is None


def test_moteur_c_plan_niveau_2_sans_oracle():
    """sk01 (jeu synthétique) : niveau 1 vu en entier + 1 coup du niveau 2 → la chaîne de C rend un plan et un programme qui
    passent la porte ; le plan gagne le niveau 2 dans le vrai moteur (utilisé ici pour fabriquer les images seulement)."""
    pytest.importorskip("clingo")
    pytest.importorskip("arc_agi")
    from pathlib import Path

    from chrysalide.arc3.logique.jeux import environnement, jouer_action, segments
    from chrysalide.arc3.moteur import MoteurC
    synth = Path("experiments/T2.8/synth_envs")
    if not (synth / "solutions.json").exists():
        pytest.skip("jeux synthétiques absents")
    gid, sols = "sk01-38abff94", json.loads((synth / "solutions.json").read_text())
    s0, s1 = segments(gid, synth, sols[gid][0] + sols[gid][1][:1])[:2]

    def lots(acts):
        return [{"actions": [{"action": NOMS[a]}]} for a in acts]
    h = {"grilles": s1["grilles"], "lots": lots(s1["actions"]),
         "precedents": [{"grilles": s0["grilles"], "lots": lots(s0["actions"]), "finale": lots([s0["finale"]])[0]}]}
    mc = MoteurC(budget=30)
    r = mc.proposer(h)
    assert r is not None, mc.infos
    plan, prog = r
    assert porte(mc, prog, h["grilles"], h["lots"]) is not None
    env = environnement(gid, synth)
    f = env.reset()
    for a in sols[gid][0] + sols[gid][1][:1] + [{v: k for k, v in NOMS.items()}[x["action"]] for x in plan]:
        f = jouer_action(env, a)
    assert f.levels_completed == 2


# ------------------------------------------------------------ CHRYS_TUTO (mini-tutoriel par niveau d'E4, dans l'agent)
def test_fc2_tuto_eteint_ou_sans_classe_inconnue_inchange(monkeypatch, tmp_path):
    """CHRYS_TUTO éteint : aucune clé tuto_ ; allumé sans CHRYS_MOTEUR : aucun effet ; allumé avec CHRYS_MOTEUR mais le
    niveau 2 ne montre aucune classe inconnue (Ligne rejoue le même niveau) : coups, trace et bilan identiques au point près."""
    pytest.importorskip("clingo")
    _eteindre(monkeypatch)
    monkeypatch.delenv("CHRYS_TUTO", raising=False)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s, m = Ligne(), Factice()
    b = branche.creer(s, tmp_path / "off", moteur=m)
    t_off = _scenario(b, s, n=8)
    assert s.niveaux >= 2 and not any(k.startswith("tuto_") for k in b.bilan())
    monkeypatch.setenv("CHRYS_TUTO", "1")
    s2, m2 = Ligne(), Factice()
    b2 = branche.creer(s2, tmp_path / "on", moteur=m2)
    assert _scenario(b2, s2, n=8) == t_off and s2.appels_modele == s.appels_modele and m2.appels == m.appels
    bl = b2.bilan()
    assert (bl["tuto_niveaux"], bl["tuto_coups"], bl["tuto_classes"]) == (0, 0, 0)
    assert {k: v for k, v in bl.items() if not k.startswith("tuto_")} == b.bilan()
    monkeypatch.delenv("CHRYS_MOTEUR")  # CHRYS_TUTO seul : la branche n'existe même pas
    assert branche.creer(Ligne(), tmp_path / "seul") is None


class Synth:
    """Solveur factice sur un jeu synthétique : le vrai moteur du jeu fabrique les images, l'agent n'en voit que la grille."""
    def __init__(self, gid, dossier):
        from chrysalide.arc3.logique.jeux import environnement
        self.env = environnement(gid, dossier)
        self.f, self.appels_modele = self.env.reset(), 0

    def current_frame(self):
        return SimpleNamespace(grid=self.f.frame[-1].tolist())  # entiers Python, comme les images de Franzen

    def step_env(self, arguments):
        from chrysalide.arc3.logique.jeux import jouer_action
        n0, fin = self.f.levels_completed, False
        for a in arguments["actions"]:
            self.f = jouer_action(self.env, {v: k for k, v in NOMS.items()}[a["action"]])
            fin = fin or self.f.levels_completed > n0
        return {"executed": True, "level_completed": fin, "game_over": self.f.state.name == "GAME_OVER"}

    def jouer_modele(self, a):
        self.appels_modele += 1
        self.step_env({"actions": [{"action": NOMS[a]}]})


def test_tuto_classe_inconnue_joue_journalise_rend_la_main(monkeypatch, tmp_path):
    """pa00 (synth_prog, mécanisme nouveau au niveau 2) : niveau 1 joué par le « modèle » ; au niveau 2 la théorie du niveau
    1 ignore des classes de la 1re image → coups d'expérience sans modèle (budget CHRYS_TUTO_COUPS=3), journalisés, comptés à
    part ; ensuite main au moteur (appelé sur ces observations) puis au modèle (Factice muet)."""
    pytest.importorskip("clingo")
    pytest.importorskip("arc_agi")
    from pathlib import Path
    synth = Path("experiments/T2.8/synth_prog")
    if not (synth / "solutions.json").exists():
        pytest.skip("jeux synthétiques absents")
    gid = "pa00-47ef93db"
    sol1 = json.loads((synth / "solutions.json").read_text())[gid][0]
    _eteindre(monkeypatch)
    for n, v in (("MOTEUR", "1"), ("TUTO", "1"), ("TUTO_COUPS", "3")):
        monkeypatch.setenv(f"CHRYS_{n}", v)
    s, m = Synth(gid, synth), Factice(rien=True)
    b = branche.creer(s, tmp_path, moteur=m)
    for a in sol1:  # niveau 1 : le modèle joue (le moteur muet est appelé, aucun tutoriel au niveau 1)
        assert not b.tour()
        s.jouer_modele(a)
    assert s.f.levels_completed == 1 and b.bilan()["tuto_niveaux"] == 0
    appels = m.appels
    assert b.tour() and b.tour() and b.tour()  # 3 coups d'expérience, sans modèle ni appel au moteur
    assert s.appels_modele == len(sol1) and m.appels == appels
    assert not b.tour() and m.appels == appels + 1  # budget atteint : le moteur juge ces observations, muet → modèle
    bl = b.bilan()
    assert (bl["tuto_niveaux"], bl["tuto_coups"], bl["tuto_classes"]) == (1, 3, 2) and bl["moteur_coups_plan"] == 0
    lignes = [json.loads(x) for x in b.trace.read_text().splitlines()]
    tuto = [x for x in lignes if x.get("source") == "tuto"]
    assert tuto[0]["ouverture"] and tuto[0]["classes"] == [7, 8] and tuto[-1]["fin"] == "budget"
    assert sum("lot" in x for x in tuto) == 3 and len(b.hist["lots"]) == 3
    assert b.raison == "classe_inconnue"  # CW-133 : le tutoriel n'a pas suffi, le modèle a la main pour cette raison
    s.jouer_modele(1)
    assert not b.tour() and b.bilan()["tuto_coups"] == 3  # une seule fois par niveau


# ------------------------------------------------------------ déclencheurs (CW-133) et ligne d'état (CW-134 P10)
def _jauge():
    """_droite(1) + jauge cachée : RIGHT consomme 1 de « jauge » (10 au départ)."""
    p = _droite(1)
    p["etat"] = {"jauge": 10}
    p["regles"][0]["alors"].append(["consommer", "jauge", 1])
    return p


def _raisons(b):
    lignes = [json.loads(x) for x in b.trace.read_text().splitlines()]
    return [x.get("declencheur") for x in lignes if x.get("source") == "modele"]


def test_sans_but_et_ligne_d_etat_exacte(monkeypatch, tmp_path):
    from chrysalide.arc3 import outils_repl
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s, m = Ligne(), Factice(plan=(), prog=_jauge())  # théorie juste, aucun plan
    s.analyzer = SimpleNamespace(generated_tokens=900)
    b = branche.creer(s, tmp_path, moteur=m)
    assert not b.tour() and b.raison == "debut_jeu" and s.analyzer._chrys_etat is None
    s.jouer_modele()
    assert not b.tour() and b.raison == "sans_but" and b.suivi is not None
    ligne = "State attributes of the verified theory (it replays every frame of this level exactly): jauge=9."
    assert s.analyzer._chrys_etat == ligne and ligne in outils_repl.ligne_tour(s.analyzer)
    s.jouer_modele()  # la théorie suivie prédit aussi les coups du modèle : la jauge reste exacte
    assert not b.tour() and s.analyzer._chrys_etat.endswith("jauge=8.")
    s.jouer_modele()  # 3e RIGHT : niveau réussi (prédit), la théorie du niveau est oubliée
    assert b.suivi is None and b.bilan()["jetons_llm_par_niveau_gagne"] == 900.0
    assert _raisons(b) == ["debut_jeu", "sans_but", "sans_but"]
    assert '"ne_rejoue_plus"' not in b.trace.read_text()
    monkeypatch.delenv("CHRYS_MOTEUR")  # drapeau éteint : ligne_tour inchangé même si l'attribut traîne
    assert outils_repl.ligne_tour(s.analyzer) == []


def test_contre_exemple_divergence_et_porte(monkeypatch, tmp_path):
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s, m = Ligne(), Factice(plan=("RIGHT",) * 5)
    b = branche.creer(s, tmp_path, moteur=m)
    s.jouer_modele()
    s.pas = 0  # RIGHT ne bouge plus : le coup du plan diverge sans finir le niveau
    assert b.tour() and not b.tour() and b.raison == "contre_exemple"  # divergence du plan
    s2, m2 = Ligne(), Factice(prog=_droite(2))
    b2 = branche.creer(s2, tmp_path / "porte", moteur=m2)
    s2.jouer_modele()
    assert not b2.tour() and b2.raison == "contre_exemple"  # la porte refuse
    assert b2.bilan()["declencheurs"]["contre_exemple"] == 1


def test_theorie_suivie_contredite_par_un_coup_du_modele(monkeypatch, tmp_path):
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s, m = Ligne(), Factice(plan=())
    b = branche.creer(s, tmp_path, moteur=m)
    s.jouer_modele()
    assert not b.tour() and b.raison == "sans_but"
    s.pas = 0  # la loi change sous les coups du modèle : la théorie suivie ne prédit plus
    s.jouer_modele()
    assert b.suivi is None and '"ne_rejoue_plus": true' in b.trace.read_text()
    m.prog = _droite(1)
    assert not b.tour() and b.raison == "contre_exemple"


def test_part_coups_moteur_et_rappel(monkeypatch, tmp_path):
    from chrysalide.arc3 import outils_repl
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    vus = []

    def corrige(br, raison, nouveau):
        vus.append((raison, nouveau))
        return "Fix the laws." if raison == "debut_jeu" else None
    s, m = Ligne(), Factice()
    s.analyzer = SimpleNamespace()
    b = branche.creer(s, tmp_path, moteur=m, rappels={"debut_jeu": corrige})
    assert not b.tour() and outils_repl.ligne_tour(s.analyzer) == ["Fix the laws."]
    s.jouer_modele()
    assert b.tour() and b.tour()  # 2 coups du plan : niveau réussi
    bl = b.bilan()
    assert bl["part_coups_moteur"] == round(2 / 3, 3) and bl["jetons_llm_par_niveau_gagne"] is None
    assert vus == [("debut_jeu", True)] and bl["declencheurs"]["debut_jeu"] == 1


class FaibleFactice(MoteurFormel):
    """Moteur à porte propre (comme MoteurCle) : programme None, portes porte1_c / porte2_c dans infos."""
    porte_propre = True

    def __init__(self, p1=True, p2=True):
        self.p1, self.p2, self.appels, self.infos, self.budget = p1, p2, 0, {}, None

    def proposer(self, historique):
        self.appels += 1
        self.infos = {"porte1_c": self.p1, "porte2_c": self.p2, "cpu_s": 0.001}
        return [{"action": "RIGHT"}, {"action": "RIGHT"}], None


def test_porte_faible_comptee_a_part_coup_par_coup(monkeypatch, tmp_path):
    """CW-154 : programme non exportable → portes faibles du moteur, comptées à part ; un seul coup joué par appel
    (redemandé sur l'historique réel) ; niveau gagné sous porte faible dit en clair ; budget 120 s au 1er appel du niveau."""
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s, m = Ligne(), FaibleFactice()
    b = branche.creer(s, tmp_path, moteur=m)
    s.jouer_modele()
    assert b.tour() and m.budget == 120.0  # 1er appel du niveau : budget long
    assert b.tour() and m.appels == 2 and m.budget is None  # redemandé après le coup réel ; budget par défaut ensuite
    bl = b.bilan()
    assert (bl["moteur_porte1_c_ok"], bl["moteur_porte2_c_ok"], bl["moteur_coups_porte_faible"]) == (2, 2, 2)
    assert bl["moteur_porte1_ok"] == 0 and bl["moteur_porte2_ok"] == 0  # jamais fusionnées avec les portes du langage
    assert bl["moteur_niveaux_porte_faible"] == 1 and bl["coups_plan_par_niveau"][0]["porte_faible"] is True


def test_porte_faible_refusee_rend_la_main(monkeypatch, tmp_path):
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s, m = Ligne(), FaibleFactice(p1=False)
    b = branche.creer(s, tmp_path, moteur=m)
    s.jouer_modele()
    assert not b.tour() and m.appels == 1  # porte1_c refusée : la main au modèle
    assert b.bilan()["moteur_porte1_c_refus"] == 1


class LigneFilm(Ligne):
    """Comme Ligne, mais exécute le lot action par action via `_execute_action` (comme le solveur de Franzen), avec un
    `animation_record` par action."""
    def _execute_action(self, a):
        fin = False
        if a["action"] == "RIGHT":
            self.n += self.pas
            if self.n >= 3:
                fin, self.n, self.niveaux = True, 0, self.niveaux + 1
        self._dessiner()
        self.animation_record = {"chain": [self.g, self.g]}
        return {"level_completed": fin}

    def step_env(self, arguments):
        fin = False
        for a in arguments["actions"]:
            fin = self._execute_action(a)["level_completed"] or fin
            if fin:
                break
        return {"executed": True, "level_completed": fin, "game_over": False}


def test_lot_multiple_decoupe_en_transitions_avec_films(monkeypatch, tmp_path):
    """CW-166 : un lot de 2 actions arrive au moteur comme 2 transitions d'une action, chacune avec son film."""
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s, m = LigneFilm(), Factice(rien=True)
    b = branche.creer(s, tmp_path, moteur=m)
    s.step_env({"actions": [{"action": "RIGHT"}, {"action": "RIGHT"}]})
    assert [len(lot["actions"]) for lot in b.hist["lots"]] == [1, 1] and len(b.hist["grilles"]) == 3
    assert len(b.hist["films"]) == 2 and all(f is not None and len(f) == 2 for f in b.hist["films"])
    s.step_env({"actions": [{"action": "RIGHT"}]})  # 3e case : niveau fini ; la finale est d'une action
    assert b.precedents and b.precedents[0]["finale"] == {"actions": [{"action": "RIGHT"}]}


def test_sans_moteur_execute_action_intact(monkeypatch, tmp_path):
    _eteindre(monkeypatch)
    s = LigneFilm()
    orig = s._execute_action
    assert branche.creer(s, tmp_path) is None and s._execute_action == orig  # F-C2 : rien n'est enveloppé


def test_porte_faible_chemin_sans_surprise(monkeypatch, tmp_path):
    """CW-177.1 : porte1_c fausse (surprise ailleurs dans le niveau) mais chemin du plan sans surprise → plan joué."""
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s, m = Ligne(), FaibleFactice(p1=False)
    orig = m.proposer

    def proposer(h):
        r = orig(h)
        m.infos["chemin_sans_surprise_c"] = True
        return r
    m.proposer = proposer
    b = branche.creer(s, tmp_path, moteur=m)
    s.jouer_modele()
    assert b.tour() and b.bilan()["moteur_coups_porte_faible"] == 1


class MurFactice(FaibleFactice):
    """Porte faible toujours vraie, plan = LEFT (Ligne n'a d'effet que sur RIGHT : coup sans effet, comme un mur)."""
    def proposer(self, historique):
        self.appels += 1
        self.infos = {"porte1_c": True, "porte2_c": True, "cpu_s": 0.001}
        return [{"action": "LEFT"}], None


def test_porte_faible_coup_sans_effet_rend_la_main(monkeypatch, tmp_path):
    """E2E4 : un coup du moteur sans effet (contre un mur) = divergence ; le moteur attend un coup du modèle."""
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s, m = Ligne(), MurFactice()
    b = branche.creer(s, tmp_path, moteur=m)
    s.jouer_modele()
    assert b.tour()  # le moteur joue LEFT : sans effet
    assert not b.tour() and m.appels == 1  # main au modèle, le moteur n'est pas redemandé
    s.jouer_modele()
    assert b.tour() and m.appels == 2  # après un coup du modèle, il reprend
    assert b.bilan()["moteur_faible_sans_effet"] == 2


def test_journal_ne_fait_jamais_tomber_l_agent(monkeypatch, tmp_path):
    """E2E4 : infos du moteur à clés non textuelles (tuples) → la trace s'écrit quand même, sans exception."""
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    s, m = Ligne(), Factice(rien=True)
    b = branche.creer(s, tmp_path, moteur=m)
    b._noter({"source": "moteur", "cle_reinduction": {(1, 2): {3: object()}}, "ensemble": {1, 2}})
    assert '"1, 2"' in b.trace.read_text() or "(1, 2)" in b.trace.read_text()


def test_plafond_cpu_par_jeu(monkeypatch, tmp_path):
    """CHRYS_MOTEUR_CPU_JEU_S : au-delà, le moteur n'est plus appelé de la partie (Franzen seul)."""
    _eteindre(monkeypatch)
    monkeypatch.setenv("CHRYS_MOTEUR", "1")
    monkeypatch.setenv("CHRYS_MOTEUR_CPU_JEU_S", "0.0001")
    s, m = Ligne(), MurFactice()
    b = branche.creer(s, tmp_path, moteur=m)
    b.m["cpu_s"] = 1.0
    s.jouer_modele()
    assert not b.tour() and m.appels == 0 and b.bilan()["moteur_plafond_cpu_atteint"] == 1


def test_but_suppose_au_niveau_1(monkeypatch):
    """D : sans niveau réussi, CHRYS_BUT_SUPPOSE=1 essaie les buts candidats non réfutés (ordre du catalogue humain) ;
    éteint, refus « pas de but » comme avant (F-C2). Le plan rendu passe les portes 1 et 2 (but supposé)."""
    pytest.importorskip("clingo")
    pytest.importorskip("arc_agi")
    from pathlib import Path

    from chrysalide.arc3.logique.jeux import segments
    from chrysalide.arc3.moteur import MoteurC, porte_but
    synth = Path("experiments/T2.8/synth_envs")
    if not (synth / "solutions.json").exists():
        pytest.skip("jeux synthétiques absents")
    gid, sols = "sk01-38abff94", json.loads((synth / "solutions.json").read_text())
    s0 = segments(gid, synth, sols[gid][0])[0]
    h = {"grilles": s0["grilles"], "lots": [{"actions": [{"action": NOMS[a]}]} for a in s0["actions"]], "precedents": []}
    monkeypatch.delenv("CHRYS_BUT_SUPPOSE", raising=False)
    mc = MoteurC(budget=30)
    assert mc.proposer(h) is None and "pas de but" in mc.infos["refus"]
    monkeypatch.setenv("CHRYS_BUT_SUPPOSE", "1")
    mc = MoteurC(budget=30)
    r = mc.proposer(h)
    assert r is not None, mc.infos
    assert mc.infos["but_suppose"]
    n, _ = porte_but(mc, r[1], h["grilles"], h["lots"], r[0])
    assert n is not None
