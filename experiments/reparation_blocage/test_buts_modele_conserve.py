import copy
from types import SimpleNamespace
from buts_modele_conserve import candidats, chercher
from test_revision_solidite import cas


def test_buts_sur_modele_repare_sans_reinduction_ni_changement_physique():
    a, _, _ = cas()
    source = next(c for c in a.chaines.values()
                  if hasattr(c, 'revision_locale') and c.perception.tr.s == 1)
    avant = copy.deepcopy(source.perception.th_releve)
    signature = source.signature()
    trouves = list(candidats(source, [('UP',), ('DOWN',)]))
    assert trouves
    for but, c in trouves:
        th = copy.deepcopy(c.perception.th_releve)
        th.but = avant.but
        assert th == avant
        assert c.actions == [('UP',), ('DOWN',)]
        assert c.rejouer()[1] is not None
    assert source.signature() == signature
    assert source.perception.th_releve == avant


def test_sans_modele_pas_de_plan_invente():
    assert chercher({}, [('UP',)])[0] is None
    assert list(candidats(SimpleNamespace(perception=object()), [('UP',)])) == []


def _source_legere(etats, grilles):
    from chrysalide.arc3.logique.theorie import Theorie
    from chrysalide.arc3.logique.export_langage import exporter
    th = Theorie()
    tr = SimpleNamespace(etats=etats, taille=(4, 4), etat=lambda grille: grille)
    programme, non = exporter(th, tr.taille)
    assert not non
    return SimpleNamespace(perception=SimpleNamespace(th_releve=th, tr=tr),
                           programme=programme, grilles=grilles, refute=False,
                           rejouer=lambda: ({}, object()))


def test_but_atteint_apres_induction_exclu(monkeypatch):
    import buts_modele_conserve as module
    from chrysalide.arc3.logique import induction
    from chrysalide.arc3.moteur import _candidats_buts
    but = ('sortie', 1, 2)
    forme = frozenset({(0, 0)})
    depart = ((1, forme, 0, 0), (2, forme, 2, 0))
    arrivee = ((1, forme, 2, 0), (2, forme, 2, 0))
    source = _source_legere([depart], [depart, arrivee])
    monkeypatch.setenv('CHRYS_BUT_CENTRE', '0')
    monkeypatch.setenv('CHRYS_MEMOIRE', '0')
    monkeypatch.setattr(induction, 'buts_candidats', lambda th, couleurs: [but])
    assert but in _candidats_buts(source.perception.th_releve, source.perception.tr)
    monkeypatch.setattr(module, 'Chaine', lambda *a, **k: (_ for _ in ()).throw(
        AssertionError('But deja atteint : aucune chaine ne doit etre construite')))
    assert list(candidats(source, [('RIGHT',)])) == []
    assert source.perception.tr.etats == [depart]


def test_source_non_synchronisee_refusee(monkeypatch):
    import buts_modele_conserve as module
    source = _source_legere([()], [()])
    source.programme['regles'].append({'nom': 'patch absent de la theorie'})
    monkeypatch.setattr(module, '_candidats_buts', lambda *a: (_ for _ in ()).throw(
        AssertionError('Une source non synchronisee ne doit pas fournir de buts')))
    assert list(candidats(source, [('UP',)])) == []


def test_plan_refuse_puis_candidat_suivant_accepte(monkeypatch):
    import buts_modele_conserve as module
    premier = SimpleNamespace(plan={'actions': [['LEFT']]},
        proposer=lambda **kw: {'statut': 'plan_simule_valide'})
    suivant = SimpleNamespace(plan={'actions': [['RIGHT']]},
        proposer=lambda **kw: {'statut': 'plan_simule_valide'})
    monkeypatch.setattr(module, 'candidats', lambda *a, **kw:
        iter([(('premier',), premier), (('suivant',), suivant)]))
    visites = []
    def accepter(action):
        visites.append(action)
        return action != ['LEFT']
    obtenu, essais = chercher({'source': object()}, [('LEFT',), ('RIGHT',)],
                              accepter=accepter)
    assert obtenu is suivant
    assert visites == [['LEFT'], ['RIGHT']]
    assert [e['but'] for e in essais] == [('premier',), ('suivant',)]


def test_roles_visites_avant_portefeuille_et_budget_partage(monkeypatch):
    import buts_modele_conserve as module
    horloge = [0.]
    visites = []
    import plan_parite
    monkeypatch.setattr(plan_parite, 'proposer_chaine', lambda c: {'statut':'hors_contrat'})
    roles = ('neutre', 'meme', 'autre')
    import plan_parite
    monkeypatch.setattr(plan_parite, 'proposer_chaine', lambda c: {'statut':'hors_contrat'})
    base = ('motif_rel', 1, 2)
    def chaine(role):
        c = SimpleNamespace(plan={'actions': [['RIGHT']]})
        def proposer(secondes, methode='but', **kw):
            visites.append((role, methode, secondes))
            horloge[0] += secondes
            return {'statut': 'plan_simule_valide' if
                    methode == 'portefeuille' and role == 'autre' else 'sans_plan'}
        c.proposer = proposer
        return c
    cs = [chaine(r) for r in roles]
    monkeypatch.setattr(module.time, 'monotonic', lambda: horloge[0])
    monkeypatch.setattr(module, 'candidats', lambda *a, **kw:
                        iter([(base + (r,), c) for r, c in zip(roles, cs)]))
    obtenu, essais = chercher({'source': object()}, [], secondes=12,
                              but_prioritaire=base, processus=4)
    assert obtenu is cs[2]
    assert [(r, m) for r, m, _ in visites] == [
        *[(r, 'but') for r in roles], *[(r, 'portefeuille') for r in roles]]
    assert [b for _, m, b in visites if m == 'portefeuille'] == [3.75] * 3
    assert horloge[0] == 12


def test_plan_deuxieme_role_petite_passe_sans_gros_portefeuille(monkeypatch):
    import buts_modele_conserve as module
    horloge = [0.]
    visites = []
    import plan_parite
    monkeypatch.setattr(plan_parite, 'proposer_chaine', lambda c: {'statut':'hors_contrat'})
    base = ('motif_rel', 1, 2)
    def chaine(role):
        c = SimpleNamespace(plan={'actions': [['RIGHT']]})
        def proposer(secondes, methode='but', **kw):
            visites.append((role, methode))
            horloge[0] += secondes
            return {'statut': 'plan_simule_valide' if role == 'meme' else 'sans_plan'}
        c.proposer = proposer
        return c
    cs = [chaine(r) for r in ('neutre', 'meme', 'autre')]
    monkeypatch.setattr(module.time, 'monotonic', lambda: horloge[0])
    monkeypatch.setattr(module, 'candidats', lambda *a, **kw:
                        iter([(base + (i,), c) for i, c in enumerate(cs)]))
    obtenu, _ = chercher({'source': object()}, [], secondes=12,
                         but_prioritaire=base, processus=4)
    assert obtenu is cs[1]
    assert visites == [('neutre', 'but'), ('meme', 'but')]


def test_backend_parite_prioritaire_avant_generique(monkeypatch):
    import buts_modele_conserve as module
    import plan_parite
    c=SimpleNamespace(plan={'actions':[['MOUSE',4,4]]}, proposer=lambda **kw: (_ for _ in ()).throw(AssertionError('generique inutile')))
    base=('motif_rel',1,2)
    monkeypatch.setattr(module,'candidats',lambda *a,**kw:iter([(base+((3,),),c)]))
    visites=[]
    def parite(candidat):
        visites.append(candidat)
        return {'statut':'plan_simule_valide','plan':candidat.plan}
    monkeypatch.setattr(plan_parite,'proposer_chaine',parite)
    obtenu,essais=chercher({'modele':object()},[],but_prioritaire=base)
    assert obtenu is c and visites==[c]
    assert essais[0]['parite']['statut']=='plan_simule_valide'
