"""Bilan des passages de développement : toutes les actions et RESET compris."""
import hashlib
import json
from pathlib import Path

ICI = Path(__file__).resolve().parent
NOMS = ['dev_ref_g0', 'dev_off_g0', 'dev_rep_g0', 'dev_locale_g0', 'dev_off_v2_g0']


def main():
    sorties, signatures = {}, {}
    for nom in NOMS:
        racine = ICI / 'runs' / nom
        resume = json.loads((racine / 'resume.json').read_text())
        info = {'niveaux': 0, 'coups': 0, 'resets': 0, 'jeux': resume, 'niveaux_detail': [], 'evenements': []}
        signatures[nom] = {}
        for jeu in sorted(resume):
            resultats = json.loads((racine / jeu / 'resultat.json').read_text())
            for r in resultats:
                p = racine / jeu / f"N{r['niveau']}" / 'partie.json'
                rows = json.loads(p.read_text())['rows']
                assert len(rows) == r['coups']
                actions = [row['action'] for row in rows]
                signatures[nom][jeu, r['niveau']] = actions
                info['niveaux'] += int(r['victoire'])
                info['coups'] += len(rows)
                info['resets'] += r['resets']
                info['niveaux_detail'].append({'jeu': jeu, 'niveau': r['niveau'], 'victoire': r['victoire'],
                    'coups': len(rows), 'resets': r['resets'], 'gagnant': r['gagnant'],
                    'actions_sha256': hashlib.sha256(json.dumps(actions).encode()).hexdigest()})
            journal = [json.loads(l) for l in (racine / jeu / 'journal_jeu.jsonl').read_text().splitlines()]
            info['evenements'].extend(dict(jeu=jeu, **r) for r in journal
                if r['type'] in ('reparation_locale', 'reparation_blocage')
                or (r['type'] == 'moteur' and r.get('reprise_blocage') == 1))
        sorties[nom] = info
    for nom in ('dev_off_g0', 'dev_off_v2_g0'):
        assert signatures[nom] == signatures['dev_ref_g0'], nom
    rapport = {'passages': sorties, 'controles_eteints_identiques': True,
                   'coups_reels_tous_essais': sum(x['coups'] for x in sorties.values()),
                   'resets_tous_essais': sum(x['resets'] for x in sorties.values()),
                   'gain_net_v1': sorties['dev_rep_g0']['niveaux']-sorties['dev_ref_g0']['niveaux'],
                   'gain_net_v2': sorties['dev_locale_g0']['niveaux']-sorties['dev_ref_g0']['niveaux']}
    (ICI / 'bilan.json').write_text(json.dumps(rapport, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in rapport.items() if k != 'passages'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
