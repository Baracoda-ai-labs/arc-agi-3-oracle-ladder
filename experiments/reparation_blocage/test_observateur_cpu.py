"""Protocoles d'isolation et de fraîcheur : aucune action ni temporisation de performance."""
import threading

from observateur_cpu import Observateur, cle_instantane


class Factice:
    def __init__(self, erreur=False):
        self.entree, self.sortie = threading.Event(), threading.Event()
        self.historique, self.erreur, self.ferme = None, erreur, False

    def proposer(self, historique, **kw):
        self.entree.set()
        if not self.sortie.wait(3):
            raise TimeoutError('test non libere')
        self.historique = historique
        if self.erreur:
            raise ValueError('echec volontaire')
        return {'statut': 'test', 'coups': kw['coup']}

    def fermer(self):
        self.ferme = True
        self.sortie.set()


def test_soumission_non_bloquante_copie_et_absence_de_file():
    d, h, ctx = Factice(), {'grilles': [[[1]]], 'lots': []}, {'partie': 'a', 'niveau': 1, 'coup': 0}
    s = Observateur(d)
    try:
        r = s.soumettre(h, ctx)
        assert d.entree.wait(1)
        assert s.lire(r['cle'])['statut'] == 'en_cours'
        assert s.soumettre(h, ctx)['statut'] == 'occupe_sans_file'
        h['grilles'][0][0][0] = 9
        ctx['coup'] = 10
        d.sortie.set()
        s.future.result(timeout=2)
        rep = s.lire(r['cle'])
        assert not rep['perime'] and not rep['droit_action']
        assert d.historique['grilles'][0][0][0] == 1
        assert rep['contexte']['coup'] == 0
        assert s.lire(r['cle'])['statut'] == 'absent'
    finally:
        s.fermer()
    assert d.ferme and s.soumettre(h, ctx)['statut'] == 'ferme'


def test_meme_image_autre_niveau_partie_ou_revision_est_perime():
    h = {'grilles': [[[1]]], 'lots': []}
    ctx = {'partie': 'a', 'niveau': 1, 'coup': 0}
    cle = cle_instantane(h, ctx)
    for autre in ({**ctx, 'partie': 'b'}, {**ctx, 'niveau': 2}, {**ctx, 'coup': 1}):
        assert cle_instantane(h, autre) != cle
    d, s = Factice(), None
    try:
        s = Observateur(d)
        s.soumettre(h, ctx)
        d.sortie.set()
        s.future.result(timeout=2)
        assert s.lire(cle_instantane(h, {**ctx, 'coup': 1}))['perime']
    finally:
        if s:
            s.fermer()


def test_erreur_et_fermeture_sans_action():
    from concurrent.futures import wait
    d, s = Factice(erreur=True), None
    try:
        s = Observateur(d)
        r = s.soumettre({'grilles': [], 'lots': []}, {'coup': 0})
        d.sortie.set()
        assert not wait([s.future], timeout=2).not_done
        rep = s.lire(r['cle'])
        assert rep['statut'] == 'erreur' and not rep['droit_action']
    finally:
        if s:
            s.fermer()
