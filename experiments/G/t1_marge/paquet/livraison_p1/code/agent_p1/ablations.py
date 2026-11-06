"""Ablations obligatoires (brief §9) sur g50t N6, mêmes conditions : niveau injecté set_level(5), budget 150.
 base         : solveur de référence sans inventeur = agent v4 d'Astra inchangé
 parametres   : recherche de paramètres seulement (familles existantes)
 sans_experience : mutations structurelles, plan de l'hypothèse de tête, aucune expérience choisie
 complet      : inventeur + diagnostic + expériences risque/plan
 gain_info, aleatoire : contrôles de la sélection d'expérience
Chaque variante écrit son dossier ; rien n'est écrasé (suffixe si le dossier existe)."""
import json, sys, time
from pathlib import Path


def run(variantes, sortie, level=6, budget=150):
    root = Path(sortie); root.mkdir(parents=True, exist_ok=True); res = []
    for v in variantes:
        d = root / v
        if d.exists():
            d = root / f'{v}_{time.strftime("%H%M%S")}'
        t0 = time.monotonic()
        if v == 'base':
            from boucle_v4.agent_fantome import run as v4
            r = v4(level, 'jeux', d, budget, 90)
            ligne = dict(variante=v, victoire=r['victory'], actions=r['actions'], raison=r['reason'],
                         hypotheses_generees=0, hypotheses_refutees=0, mecanismes_valides=0)
        else:
            from .agent import Agent
            r = Agent('g50t', level, 'jeux', d, v, budget, 900).run()
            ligne = dict(variante=v, victoire=r['victoire'], actions=r['actions'], raison=r['raison'],
                         hypotheses_generees=r['hypotheses_generees'], hypotheses_refutees=r['hypotheses_refutees'],
                         refutations_par_intervention=r['refutations_par_intervention'],
                         mecanismes_survivants=len(r['mecanismes']), defauts_ARC=r.get('defauts_ARC'))
        ligne['secondes'] = round(time.monotonic() - t0, 1); ligne['dossier'] = str(d)
        res.append(ligne)
        (root / 'ablations.json').write_text(json.dumps(res, indent=1, default=str, ensure_ascii=False))
        print(json.dumps(ligne, default=str), flush=True)
    return res


if __name__ == '__main__':
    run(sys.argv[2].split(','), sys.argv[1])
