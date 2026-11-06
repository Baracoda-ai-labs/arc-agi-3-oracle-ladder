"""Contrôle préinscrit ft09 : même compilation, même porte, suivi ATMS sur trace."""
import json
from pathlib import Path

from banc_observateur import charger
from chaine_coherente import Chaine

from chrysalide.arc3.moteur import MoteurC, nom_action


def main():
    from agent_p1.releve_coherent import actions_reprise
    sortie = Path(__file__).with_name('bilan_cegar_atms.json')
    if sortie.exists():
        raise FileExistsError(sortie)
    hist, doc, images, ctx = charger(('publics_ref_g0', 'ft09', 1, 80))
    m = MoteurC(budget=2)
    r = m.proposer(hist)
    assert r and r[1]
    plan = [a if 'action' in a else a['actions'][0] for a in r[0]]
    c = Chaine(m, r[1], hist['grilles'], hist['lots'], actions_reprise(m, plan),
               coups_deja_joues=80, films=hist['films'])
    c.activer_atms()
    resultat = c.proposer(methode='cegar', secondes=.5)
    bilan = {'nouveaux_appels_sdk': 0, 'appels_ia': 0, 'cas': ctx, 'cegar': resultat,
             'observations': [], 'victoire_nouvelle': False}
    if resultat['statut'] == 'plan_simule_valide':
        actions = resultat['plan']['actions']
        from agent_p1.releve_moteur import _lot
        for i, a in enumerate(actions):
            k = 80 + i
            if k >= len(doc['rows']) or tuple(a) != nom_action(_lot(doc['rows'][k]['action'])['actions'][0]):
                bilan['observations'].append({'statut': 'action_differente_non_verifiable'})
                break
            victoire = bool(doc['victory']) and k + 1 == len(doc['rows'])
            obs = c.observer(a, images[k + 1], victoire=victoire, source='trace')
            bilan['observations'].append(obs)
            if obs['statut'] != 'transition_confirmee':
                break
            if i + 1 < len(actions):
                c.adopter_plan(actions[i + 1:])
    bilan['atms'] = c.atms.rapport()
    sortie.write_text(json.dumps(bilan, ensure_ascii=False, indent=2, default=repr) + '\n')
    print(json.dumps({'cegar': resultat['statut'], 'infos': resultat.get('infos'),
                      'observations': bilan['observations']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
