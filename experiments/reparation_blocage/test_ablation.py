"""Réfutation d'un but et préservation de l'apprentissage, sans jeu."""
import copy
from types import SimpleNamespace

from ablation import diagnostiquer
from test_chaine_coherente import exemple


def test_ablation_faux_but_ne_revient_pas_a_une_victoire():
    c, image = exemple()
    c.proposer()
    c.observer(('RIGHT',), image(5))
    c.proposer()
    c.observer(('RIGHT',), image(6), victoire=False)
    avant = copy.deepcopy(c.programme)
    bilan, candidats = diagnostiquer(c)
    assert bilan['statut'] == 'hypothese_unique'
    assert len(candidats) == 1
    assert c.refute and c.programme == avant and c.version == 1
    assert candidats[0].rejouer()[0]['rejeu']
    assert candidats[0].proposer(secondes=.01)['statut'] != 'plan_simule_valide'


def test_supprimer_mouvement_qui_explique_le_passe_est_refuse():
    c, image = exemple()
    c.proposer()
    c.observer(('RIGHT',), image(4))
    bilan, candidats = diagnostiquer(c)
    assert bilan['exploration_complete'] and not candidats
    assert bilan['statut'] == 'aucune_reparation_trouvee'


def test_actions_reprise_conserve_alternative_absente_du_plan():
    from agent_p1.releve_coherent import actions_reprise
    moteur = SimpleNamespace(tr=SimpleNamespace(actions=[1, 4, 1, 7]), th_plan=None)
    actions = actions_reprise(moteur, [{'action': 'RIGHT'}])
    assert actions == [('UP',), ('RIGHT',)]
