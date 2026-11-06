"""Garanties sur graphes finis et justifications explicites, sans victoire ARC revendiquée."""
import copy

import pytest
from atms import ATMS, LimiteATMS
from cegar import chercher
from test_chaine_coherente import exemple


def test_cegar_elimine_chemin_fallacieux_avant_plan_concret():
    g = {0: {'a': 1, 'b': 2}, 1: {}, 2: {'c': 3}, 3: {}}
    plan, infos = chercher(g, 0, {3}, complet=True)
    assert plan == ['b', 'c']
    assert infos['raffinements'] and infos['statut'] == 'plan_concret_verifie'
    s = 0
    for a in plan:
        s = g[s][a]
    assert s == 3


def test_cegar_pas_de_certificat_sur_graphe_tronque_ou_budget():
    assert chercher({0: {}}, 0, set(), complet=False)[1]['statut'] == 'inconnu_graphe_tronque'
    assert chercher({0: {}}, 0, set(), complet=True)[1]['statut'] == 'inaccessible_dans_modele'
    assert chercher({0: {}}, 0, set(), complet=True, secondes=0)[1]['statut'] == 'budget'


def test_cegar_refuse_graphe_mal_forme():
    with pytest.raises(ValueError):
        chercher({0: {'a': 1}}, 0, set())


def test_atms_alternatives_et_conjonction_minimales():
    t = ATMS()
    for h in ('a', 'b', 'c'):
        t.supposer(h)
    t.justifier('x', ['a'])
    t.justifier('x', ['b'])
    t.justifier('x', ['a', 'c'])
    t.justifier('y', ['x', 'c'])
    assert t.labels['x'] == {frozenset({'a'}), frozenset({'b'})}
    assert t.labels['y'] == {frozenset({'a', 'c'}), frozenset({'b', 'c'})}
    t.interdire({'a', 'c'})
    assert t.tient('y', {'b', 'c'}) and not t.tient('y', {'a', 'c'})
    assert t.tient('x', {'a'})  # le contexte contradictoire n'accuse pas a seul


def test_atms_contradiction_derivee_et_noeud_independant():
    t = ATMS()
    for h in ('a', 'b'):
        t.supposer(h)
    t.fait('observation')
    t.justifier('prediction', ['a', 'observation'])
    t.justifier('autre', ['b'])
    t.justifier(t.FAUX, ['prediction'])
    assert t.nogoods == {frozenset({'a'})}
    assert not t.tient('prediction', {'a'}) and t.tient('autre', {'b'})


def test_atms_cycles_sans_preuve_et_faits():
    t = ATMS()
    t.justifier('x', ['y'])
    t.justifier('y', ['x'])
    assert not t.labels['x']
    t.fait('x')
    assert t.tient('y', set())


def test_atms_depassement_transactionnel():
    t = ATMS(limite=3)
    t.supposer('a')
    ancien = copy.deepcopy(t.rapport())
    with pytest.raises(LimiteATMS):
        t.justifier('x', ['a', 'inconnu'])
    assert t.rapport() == ancien and not t.justifications


def test_chaine_cegar_utilise_la_compilation_et_la_porte():
    c, _ = exemple()
    r = c.proposer(methode='cegar', secondes=.2)
    assert r['statut'] == 'plan_simule_valide', r
    assert len(r['plan']['actions']) == 2
    assert r['infos']['backend'] == 'ProgrammeCompile'
    assert not r['infos']['preuve_sur_jeu_reel']


def test_chaine_atms_revoque_contexte_et_garde_historique():
    c, image = exemple()
    t = c.activer_atms()
    t.supposer('independant')
    t.justifier('connaissance', ['independant'])
    r = c.proposer()
    noeud = r['plan']['noeud_atms']
    contexte = r['plan']['contexte_atms']
    assert t.tient(noeud, contexte)
    c.observer(('RIGHT',), image(4))
    assert not t.tient(noeud, contexte)
    assert t.tient('connaissance', {'independant'})
    assert c.refute and c.plan is None
    assert len(t.nogoods) == 1


def test_contexte_atms_invalide_exterieurement_ne_peut_jouer():
    c, image = exemple()
    t = c.activer_atms()
    r = c.proposer()
    t.interdire(r['plan']['contexte_atms'])
    assert c.observer(('RIGHT',), image(5))['statut'] == 'contexte_atms_invalide'
    assert c.proposer()['statut'] == 'contexte_atms_invalide'


def test_atms_labels_contre_tables_verite_horn():
    # Oracle indépendant : toutes les valuations d'hypothèses, fermeture propositionnelle brute.
    from itertools import combinations
    t = ATMS()
    hypotheses = ('a', 'b', 'c')
    for h in hypotheses:
        t.supposer(h)
    justifications = [('x', ('a',)), ('x', ('b', 'c')), ('y', ('x', 'c')),
                      ('z', ('y',)), ('x', ('z',)), (t.FAUX, ('a', 'b'))]
    for conclusion, aa in justifications:
        t.justifier(conclusion, aa)
    for n in range(4):
        for choix in combinations(hypotheses, n):
            contexte, vrais = set(choix), set(choix)
            while True:
                suite = vrais | {c for c, aa in justifications if set(aa) <= vrais}
                if suite == vrais:
                    break
                vrais = suite
            for noeud in ('a', 'b', 'c', 'x', 'y', 'z'):
                assert t.tient(noeud, contexte) == (noeud in vrais and t.FAUX not in vrais)


def test_cegar_contre_bfs_sur_graphes_generes():
    import random
    from collections import deque
    rng = random.Random(42)
    for _ in range(100):
        g = {s: {a: rng.randrange(4) for a in ('a', 'b') if rng.random() < .65} for s in range(4)}
        file, vus, possible = deque([0]), {0}, False
        while file:
            s = file.popleft()
            if s == 3:
                possible = True
                break
            for v in g[s].values():
                if v not in vus:
                    vus.add(v)
                    file.append(v)
        plan, infos = chercher(g, 0, {3}, complet=True)
        assert (plan is not None) == possible, (g, infos)
        if plan is not None:
            s = 0
            for a in plan:
                s = g[s][a]
            assert s == 3


def test_cegar_atms_aussi_importables_depuis_paquet_de_releve():
    from agent_p1.chaine_coherente import Chaine
    base, _ = exemple()
    c = Chaine(base.perception, base.programme, base.grilles, base.lots, base.actions)
    c.activer_atms()
    r = c.proposer(methode='cegar', secondes=.1)
    assert r['statut'] == 'plan_simule_valide'
    assert r['plan']['contexte_atms']


def test_extensions_formelles_couvertes_par_manifest_du_paquet():
    import hashlib
    from pathlib import Path
    paquet = Path(__file__).resolve().parent / 'paquet'
    sommes = {nom: sha for sha, nom in (ligne.split(maxsplit=1)
              for ligne in (paquet / 'SHA256SUMS').read_text().splitlines())}
    for nom in ('atms.py', 'cegar.py', 'cegar_compile.py'):
        relatif = 'livraison_p1/code/agent_p1/' + nom
        assert sommes[relatif] == hashlib.sha256((paquet / relatif).read_bytes()).hexdigest()
