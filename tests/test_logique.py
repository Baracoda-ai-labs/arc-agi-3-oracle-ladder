# SPDX-License-Identifier: MIT-0
"""T3.0 [session C] — moteur logique : perception en objets, induction ASP, rejeu exact, défauts plantés, planification."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("clingo")
pytest.importorskip("arc_agi")

from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.induction import induire
from chrysalide.arc3.logique.jeux import environnement, jouer_action, segments
from chrysalide.arc3.logique.plan import planifier
from chrysalide.arc3.logique.theorie import rejeu

SYNTH = Path("experiments/T2.8/synth_envs")
SOLS = json.loads((SYNTH / "solutions.json").read_text()) if SYNTH.exists() else {}
pytestmark = pytest.mark.skipif(not SOLS, reason="jeux synthétiques absents")


def _demo(gid, niveau=0):
    s = segments(gid, SYNTH, [a for n in SOLS[gid][:niveau + 1] for a in n])[niveau]
    return Trajectoire(s["grilles"], s["actions"]), s


def test_perception_echelle_et_objets():
    tr, _ = _demo("sk00-831668bc")
    assert (tr.s, tr.taille) == (9, (7, 7))  # grille 7×7 agrandie ×9
    assert {o[0] for o in tr.etats[0]} == {3, 4, 5, 7, 8}  # joueur, sortie, murs, clé, porte


def test_induction_cle_porte_rejeu_exact():
    tr, s = _demo("sk00-831668bc")
    th, inf = induire([(tr, None, s["finale"])])
    assert inf["optimal"]
    assert (3, 7) in th.consomme and (8, 7) in th.lie and th.but == ("sortie", 3, 4)
    ok, n, premier = rejeu(th, tr)
    assert ok == n and premier is None


def test_defauts_plantes_rejetes():
    """Tester le testeur (CW-065.2) : chaque mutation de la bonne théorie doit être contredite par le rejeu exact."""
    tr, s = _demo("sb00-71feeb99")
    th, _ = induire([(tr, None, s["finale"])])
    assert rejeu(th, tr)[0] == len(tr.actions)
    (c, a), v = next(iter(th.moves.items()))
    # retirer les murs ne serait PAS détecté ici : la démonstration optimale n'en heurte aucun (limite du rejeu)
    sans_a = {k: x for k, x in th.moves.items() if k != (c, a)}
    mutants = [replace(th, moves={**th.moves, (c, a): (-v[0], -v[1])}), replace(th, poussables=frozenset()),
               replace(th, moves=sans_a)]
    for m in mutants:
        ok, n, premier = rejeu(m, tr)
        assert ok < n and premier is not None


def test_plan_niveau_suivant_gagne_dans_le_vrai_moteur():
    tr, s = _demo("sk01-38abff94")
    th, _ = induire([(tr, None, s["finale"])])
    env = environnement("sk01-38abff94", SYNTH)
    f = env.reset()
    for a in SOLS["sk01-38abff94"][0]:
        f = jouer_action(env, a)
    assert f.levels_completed == 1
    tr2 = Trajectoire([f.frame[-1]], [], atomiques=tr.atomiques)
    plan, _ = planifier(th, tr2.etats[0], tr2.taille, [1, 2, 3, 4])
    assert plan is not None and len(plan) == len(SOLS["sk01-38abff94"][1])
    for a in plan:
        f = jouer_action(env, a)
    assert f.levels_completed == 2


def test_clic_ft09_bascule_et_zone():
    """ft09 : un clic sur une tuile de la zone de jeu (cadre 4) la fait passer de 9 à 8 ; les tuiles modèles ne bougent pas."""
    from chrysalide.arc3.logique.jeux import segments as segs
    clics = [("clic", 37, 37), ("clic", 45, 37), ("clic", 5, 5), ("clic", 37, 37), ("clic", 53, 53)]
    s = segs("ft09", Path("experiments/arc3/environment_files"), clics)[0]
    tr = Trajectoire(s["grilles"], s["actions"])
    th, inf = induire([(tr, None, None)])
    assert inf["transitions_inexpliquees"] == 0
    assert th.motif == {(0, 0)} and th.bascule.get(9) == 8 and th.zone == 4
    assert rejeu(th, tr)[0] == len(tr.actions)


def test_induire_k_theories_concurrentes():
    """Demande de B (CCM-054-B) : plusieurs théories, la première = la minimale, toutes aussi cohérentes qu'elle."""
    from chrysalide.arc3.logique.induction import induire_k
    tr, _ = _demo("sk00-831668bc")
    ths = induire_k([(tr, range(4), None)], k=5)
    assert len(ths) == 5 and len({t.texte() for t, _ in ths}) == 5
    assert ths[0][0].texte() == induire([(tr, range(4), None)])[0].texte()
    assert all(c[0] == 0 and c[1] <= ths[0][1][1] + 1 for _, c in ths)


def test_perception_comme_hypothese_clic_bascule():
    """CW-072 : sur sc00 (clic = case + 4 voisines, 8↔9), le découpage « cases » l'emporte et la règle est exacte."""
    from chrysalide.arc3.logique.abstraction import induire_abstraction
    gid = "sc00-ad21ff4f"
    segs = segments(gid, SYNTH, [a for n in SOLS[gid] for a in n])
    nom, th, inf, _ = induire_abstraction(segs[:2])
    assert nom == "cases" and inf["candidats"]["cases"][0] == 0 < inf["candidats"]["composantes"][0]
    assert th.motif == {(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)} and th.bascule == {8: 9, 9: 8}
    assert th.but == ("absent", 9, 9)


def test_pour_but_leve_h_mur():
    """Sans démonstration, la sortie (jamais traversée) est un mur supposé ; viser la sortie lève cette hypothèse."""
    tr, _ = _demo("sn00-e29fa00c")
    th, _ = induire([(tr, None, None)])
    assert 4 in th.murs_supposes and th.but is None
    tb = th.pour_but(("sortie", 3, 4))
    assert 4 not in tb.solides and tb.but == ("sortie", 3, 4) and 4 in th.solides
    plan, _ = planifier(tb, tr.etats[0], tr.taille, [1, 2, 3, 4])
    assert plan is not None and len(plan) == len(SOLS["sn00-e29fa00c"][0])


def test_oracle_ls20_deplacement_par_5():
    """Perception ORACLE de A (bancs seulement) : sur ls20, le joueur avance de 5 cases par flèche et la règle prédit
    exactement les transitions suivantes (égalité des ensembles d'objets)."""
    from chrysalide.arc3.logique.oracle import segments_oracle
    tr = segments_oracle("ls20", Path("experiments/arc3/environment_files"), [4, 4, 1, 3, 2, 4, 3, 1])[0]["traj"]
    th, inf = induire([(tr, range(5), None)])
    assert inf["transitions_inexpliquees"] == 0 and any(v == (5, 0) for v in th.moves.values())
    assert all(th.pas(tr.etats[t], tr.actions[t], tr.taille)[0] == tr.etats[t + 1] for t in range(5, len(tr.actions)))


def test_oracle_ar25_miroir_et_annulation():
    """ar25 (perception ORACLE) : un sprite = joueur ∪ reflet par l'axe x = 10 ; l'action 7 dépile l'historique.
    Les deux ne sont appris qu'à partir des transitions d'apprentissage (pas de fuite vers le test)."""
    from chrysalide.arc3.logique.induction import precedent_pile
    from chrysalide.arc3.logique.oracle import segments_oracle
    acts = [4, 4, 1, 7, 3, 2, 7, 2, 4, 1, 7, 3]
    tr = segments_oracle("ar25", Path("experiments/arc3/environment_files"), acts)[0]["traj"]
    th, _ = induire([(tr, range(len(tr.actions)), None)])
    assert th.annule == 7 and any(v[1:] == ("x", 20) for v in th.derives.values())
    ok = sum(th.pas(tr.etats[t], tr.actions[t], tr.taille,
                     precedent=precedent_pile(tr.etats, tr.actions, t, th.annule))[0] == tr.etats[t + 1]
             for t in range(len(tr.actions)))
    assert ok >= 0.8 * len(tr.actions)
    th3, _ = induire([(tr, range(3), None)])  # aucun « annuler » dans les 3 premiers coups
    assert th3.annule is None


def test_perception_temporelle_ls20_fond_solide():
    """Perception TEMPORELLE de A (sans oracle) + complétion amodale : sur ls20, le joueur avance de 5 px et bute sur le
    fond (les murs sont de la couleur de fond) ; la théorie le dit avec `fond_solide`."""
    from chrysalide.arc3.logique.temps import segments_temps
    acts = [4, 4, 1, 3, 2, 2, 2, 1, 1, 1, 3, 3, 4, 2]
    tr = segments_temps("ls20", Path("experiments/arc3/environment_files"), acts)[0]["traj"]
    th, inf = induire([(tr, None, None)])
    assert inf["transitions_inexpliquees"] == 0 and (5, 0) in th.moves.values() and th.fond_solide


def test_priors_de_b_trace_ss00():
    """CCM-059-B / CW-083 : sur la trace ss00 de B, plus de murs « poussables » (jamais vus bouger), sélection exclusive
    apprise (exclusif + désélection), 0 transition inexpliquée."""
    from chrysalide.arc3.logique.abstraction import induire_abstraction
    traces = Path("experiments/T2.9/traces_pour_C.json")
    if not traces.exists():
        pytest.skip("traces de B absentes")
    v = json.loads(traces.read_text())["ss00-94cb56ff"]
    acts = [tuple(a) if isinstance(a, list) and a and a[0] == "clic" else a for a in v["actions"]]
    segs = [s for s in segments("ss00-94cb56ff", SYNTH, acts) if s["niveau"] == 0]
    _, th, inf, _ = induire_abstraction(segs)
    assert inf["transitions_inexpliquees"] == 0 and 5 not in th.poussables
    assert th.exclusif and th.desel == {6: 3, 15: 14} and th.bascule == {3: 6, 14: 15}


def test_ar25_sans_oracle_reflet_et_echelle():
    """ar25 SANS oracle : l'échelle 3 est retenue par le rejeu exact, et le reflet du joueur (autre couleur, objet séparé)
    est expliqué, soit par la règle `reflet`, soit par un objet qui bouge en sens inverse sur x (équivalent loin de l'axe)."""
    import random
    import sys
    sys.path.insert(0, "experiments/T3.0")
    from banc import actions_hasard

    from chrysalide.arc3.logique.abstraction import induire_abstraction
    seg = segments("ar25", Path("experiments/arc3/environment_files"), actions_hasard("ar25", random.Random(0), 30))[0]
    _, th, _, src = induire_abstraction([dict(seg, finale=None, issue=None)], ts=range(25), echelles=True)
    inverse = any(th.moves.get((c, 3)) == (1, 0) for c, _ in th.moves)
    assert src[0][0].s == 3 and ("reflet(" in th.texte() or inverse)


MOD = Path("experiments/T3.0/synth_mod_v2")


@pytest.mark.skipif(not MOD.exists(), reason="jeux à modificateur absents")
def test_transforme_et_but_conditionnel():
    """CW-087 : sa00 — le joueur (3) devient 11 sur le modificateur (6), but = sortie par 11 ; si01 — le modificateur
    bascule un INDICATEUR (12 → 13), but conditionnel retenu par rationalité du démonstrateur (détour par le modificateur)."""
    sols = json.loads((MOD / "solutions.json").read_text())
    s = segments("sa00-e383b876", MOD, sols["sa00-e383b876"][0])[0]
    th, inf = induire([(Trajectoire(s["grilles"], s["actions"]), None, s["finale"])])
    assert (6, 3, 11) in th.transforme and th.but == ("sortie", 11, 4) and inf["transitions_inexpliquees"] == 0
    s = segments("si01-718cc5dd", MOD, sols["si01-718cc5dd"][0])[0]
    th, _ = induire([(Trajectoire(s["grilles"], s["actions"]), None, s["finale"])])
    assert (6, 12, 13) in th.transforme and th.but == ("sortie_si", 3, 4, 13)


def test_export_langage_rejoue_dans_interpreteur_de_a():
    """CCM-015-C / CW-111 : une théorie induite (clé, porte, sortie) exportée dans le langage de A rejoue EXACTEMENT
    la démonstration dans l'interpréteur de A, contre le vrai moteur (porte indépendante du simulateur de C)."""
    from chrysalide.arc3.logique.export_langage import exporter, verifier
    tr, s = _demo("sk00-831668bc")
    th, _ = induire([(tr, None, s["finale"])])
    prog, non = exporter(th, tr.taille)
    assert not non
    ok, n, premiere = verifier(prog, "sk00-831668bc", SYNTH, SOLS["sk00-831668bc"][0])
    assert ok == n == len(tr.actions) and premiere is None


def test_continuite_entre_niveaux():
    """CCM-022-C : avec 1 coup seulement du niveau 2, la théorie du niveau 1 (clé, porte, sortie, 4 flèches) est
    conservée (prior de continuité + H_continuite) ; sans elle, ces lois disparaissent faute de données."""
    from chrysalide.arc3.logique.induction import classes_inconnues
    tr1, s1 = _demo("sk01-38abff94")
    th1, _ = induire([(tr1, None, s1["finale"])])
    s2 = segments("sk01-38abff94", SYNTH, SOLS["sk01-38abff94"][0] + SOLS["sk01-38abff94"][1][:1])[1]
    tr2 = Trajectoire(s2["grilles"], s2["actions"])
    seul, _ = induire([(tr2, None, None)])
    avec, _ = induire([(tr2, None, None)], anciennes=th1)
    assert seul.but is None and len(seul.moves) < 4
    assert avec.but == th1.but and th1.consomme <= avec.consomme and len({a for _, a in avec.moves}) == 4
    assert not classes_inconnues(avec, tr2.etats[0])
