"""Tests hors ligne (aucun coup réel). python -m mechanism_inventor.tests_inventeur
B contradiction → réparation ; D falsification avec preuve ; E budget et comptage (sur les parties jouées) ;
mémoire (une réfutée n'est jamais retestée) ; superviseur (change de famille) ; sémantique commune trace/planif ;
nouveauté (l'hypothèse retenue n'est pas exprimable dans la bibliothèque initiale)."""
import json, unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
TRACE_N6 = RACINE / 'references/astra4/livraison_astra4/tenus_ecart/g50t_N6'


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from .analyse_trace import charger, analyser
        cls.images, cls.actions = charger(TRACE_N6)
        cls.res = analyser(cls.images, cls.actions)
        cls.model = cls.res['_model']; cls.lignes = cls.res['_lignes']
        cls.obj = next(o for o in cls.res['_objs'] if o['id'] == 'obj1')

    def test_B_contradiction_reparation(self):
        r = self.res['par_objet']['obj1']
        self.assertGreater(r['n_generees'], 100)
        self.assertGreaterEqual(r['n_survivantes'], 1)
        rep = r['classes'][0]['representant']
        self.assertEqual(rep['programme']['effet'], 'couloir')
        self.assertTrue(rep['nouveaute'])  # structure absente de la bibliothèque initiale v4

    def test_D_falsification(self):
        from .hypotheses import Hypothese, programme
        from .classement import evaluer
        # miroir vertical : explique le coup 2 (BAS → objet monte) ; contredit plus tard
        h = Hypothese(id='plausible', version=1, objet='obj1', mutations=['M1'],
                      programme=programme(declencheur='coup_effectif', effet='miroir', transfo='flipy', reinit='action5'))
        evaluer([h], self.obj, self.lignes, self.model, 7)
        self.assertIn(2, h.explique)
        self.assertEqual(h.statut, 'rejetee')
        self.assertIsNotNone(h.preuve_rejet)
        self.assertIn('observe', h.preuve_rejet); self.assertIn('predit', h.preuve_rejet)

    def test_memoire_jamais_retestee(self):
        from .superviseur import superviser, Memoire
        from .mutations import contexte_causal
        from .objets import contradictions_v4
        ctx = contexte_causal(self.obj, contradictions_v4(self.res['_objs'], self.lignes), self.lignes)
        m = Memoire()
        h1, r1 = superviser(self.obj, ctx, self.lignes, self.model, 6, m, 'ctx', 1)
        rej1 = {h.id for h in h1 if h.statut == 'rejetee'}
        h2, r2 = superviser(self.obj, ctx, self.lignes, self.model, 6, m, 'ctx', 2)
        self.assertEqual(r2['sautees_memoire'], len(rej1))
        self.assertTrue(all(h.preuve_rejet.get('memoire') for h in h2 if h.id in rej1))

    def test_superviseur_change_de_famille(self):
        from .superviseur import superviser, Memoire
        from .mutations import contexte_causal
        from .objets import contradictions_v4
        ctx = contexte_causal(self.obj, contradictions_v4(self.res['_objs'], self.lignes), self.lignes)
        h, r = superviser(self.obj, ctx, self.lignes, self.model, 6, Memoire(), 'ctx', 1)
        fam = {f['famille']: f for f in r['familles']}
        self.assertTrue(fam['parametre_miroir']['abandon_apres_refutations'])
        self.assertGreater(fam['composition_couloir']['survivantes'], 0)
        hs, rs = superviser(self.obj, ctx, self.lignes, self.model, 6, Memoire(), 'ctx', 1, sans_superviseur=True)
        self.assertLess(len(h), len(hs))

    def test_semantique_commune(self):
        """Le modèle de planification reproduit les poses de l'objet que la simulation prédit sur la trace."""
        from .classement import classes_equivalence
        rep = classes_equivalence(self.res['_hyps']['obj1'])[0]['representant']
        self.assertEqual(rep.statut, 'survivante')
        self.assertFalse(rep.contredit)

    def test_E_budget_et_comptage(self):
        """Toutes les parties jouées : coups <= budget, chaque coup a un but journalisé, aucune partie écrasée."""
        n = 0
        for p in (RACINE / 'livraison_p0').rglob('partie.json'):
            d = json.loads(p.read_text())
            if not d.get('rows'):
                continue
            n += 1
            self.assertLessEqual(len(d['actions']), 150, str(p))
            self.assertEqual(len(d['actions']), len(d['rows']))
            self.assertTrue(all(r.get('purpose') for r in d['rows']))
        self.assertGreater(n, 0)


class TestReproductibleN6(unittest.TestCase):
    def test_rejeu_de_la_victoire_N6(self):
        """L'agent (code courant), nourri des images de la partie gagnante, rejoue exactement les mêmes coups
        jusqu'à la victoire (0 coup réel). Échoue si une décision diverge de la trace."""
        import tempfile
        from .rejeu import LabRejoue
        from .agent import Agent
        d = RACINE / 'livraison_p0/runs/N6_complet_essai6_final'
        if not (d / 'partie.json').exists():
            self.skipTest('partie N6 absente')
        lab = LabRejoue(d)
        r = Agent('g50t', 6, 'jeux', tempfile.mkdtemp(), 'complet', lab=lab).run()
        self.assertTrue(r['victoire'], r['raison'])
        self.assertEqual(r['actions_liste'], lab.trace_actions)


if __name__ == '__main__':
    unittest.main(verbosity=2)
