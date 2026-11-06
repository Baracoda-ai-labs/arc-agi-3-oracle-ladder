"""Comparaison appariée des explorateurs (développement) et commande de mesure.

python -m runner --jeux <dossier> --sortie <dossier> --explorateur generique|ow --mode seul|complet [--jeu ...]
            [--memoire_depart livraison_p1/memoire_depart] [--budget 150] [--memoire_par_jeu]

mode complet : agent P1 inchangé (routage v4 poussée → v4+inventeur → exploration), seul l'explorateur est remplacé.
mode seul    : exploration seule depuis RESET (sans les phases v4), pour isoler l'explorateur.
"""
import argparse, json, shutil, sys, time, traceback
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = next(p for p in ICI.parents if (p / 'livraison_p1').is_dir())
for p in (RACINE, RACINE / 'livraison_p1/code', RACINE / 'references/astra4/livraison_astra4/ajouts', ICI):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import agent_p1.jouer as J  # noqa: E402  (active les bornes en nœuds)
from agent_p1.labo import LaboP1  # noqa: E402
from agent_p1.journal import Journal, sha_code  # noqa: E402
from agent_p1.generique import Explorateur as ExplorateurGenerique  # noqa: E402


def classe(nom):
    if nom == 'generique':
        return ExplorateurGenerique
    from explo_ow import ExplorateurOW
    return ExplorateurOW


def jouer_seul(dossier, jeu, sortie, Ex, budget, memoire, max_niveaux=20, graine=0):
    out = Path(sortie) / jeu; out.mkdir(parents=True, exist_ok=True)
    mem = J.charger_memoire(memoire); mem.changer_jeu(jeu)
    j = Journal(out, 'journal_jeu', dict(jeu=jeu, budget=budget, mode='seul', explorateur=Ex.__name__))
    lab = LaboP1(jeu, 1, dossier, out / 'N1' / 'partie'); res = []
    for niveau in range(1, max_niveaux + 1):
        t0 = time.monotonic(); infos = {}
        tentative = 0
        while not lab.won and len(lab.rows) < budget and tentative < 3:
            tentative += 1
            try:
                if lab.finished and not lab.won:
                    lab.reset_apres_defaite()
                ex = Ex(lab, j, mem, graine + tentative)
                ex.jouer(budget)
                infos = getattr(ex, 'bilan', lambda: dict(etats=len(ex.aretes)))()
            except Exception as e:
                infos = dict(exception=str(e), tb=traceback.format_exc()[-1500:])
        ligne = dict(jeu=jeu, niveau=niveau, victoire=lab.won, coups=len(lab.rows), resets=lab.resets,
                     defaites=lab.defaites, secondes=round(time.monotonic() - t0, 1), infos=infos)
        res.append(ligne); j.ecrire('niveau', **ligne)
        (out / 'resultat.json').write_text(json.dumps(res, indent=1, default=str, ensure_ascii=False))
        J.sauver_memoire(memoire, mem)
        print(json.dumps({k: ligne[k] for k in ('jeu', 'niveau', 'victoire', 'coups', 'resets', 'secondes')}), flush=True)
        if not lab.won or getattr(lab, 'partie_gagnee', False):
            break
        lab = lab.next_level(out / f'N{niveau + 1}' / 'partie')
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jeux', required=True); ap.add_argument('--sortie', required=True)
    ap.add_argument('--jeu', nargs='*'); ap.add_argument('--budget', type=int, default=150)
    ap.add_argument('--explorateur', default='ow'); ap.add_argument('--graine', type=int, default=0); ap.add_argument('--mode', default='complet')
    ap.add_argument('--memoire_depart', default=str(RACINE / 'livraison_p1/memoire_depart'))
    ap.add_argument('--memoire_par_jeu', action='store_true',
                    help='développement : mémoire repartant de memoire_depart pour chaque jeu (comparaison appariée)')
    a = ap.parse_args()
    Ex = classe(a.explorateur)
    jeux = a.jeu or J.lister_jeux(a.jeux)
    tout = {}
    for g in jeux:
        memoire = Path(a.sortie) / ('memoire_' + g if a.memoire_par_jeu else 'memoire_inter_jeux')
        memoire.mkdir(parents=True, exist_ok=True)
        for f in Path(a.memoire_depart).glob('*.json'):
            if not (memoire / f.name).exists():
                shutil.copy(f, memoire / f.name)
        if a.mode == 'seul':
            r = jouer_seul(a.jeux, g, a.sortie, Ex, a.budget, memoire, graine=a.graine)
        else:
            J.Explorateur = Ex
            r = J.jouer_jeu(a.jeux, g, a.sortie, a.budget, str(memoire), graine=a.graine)
        tout[g] = r
        Path(a.sortie, 'resume.json').write_text(json.dumps(
            {g: dict(niveaux_gagnes=sum(x['victoire'] for x in r), coups=sum(x['coups'] for x in r),
                     resets=sum(x['resets'] for x in r)) for g, r in tout.items()}, indent=1))


if __name__ == '__main__':
    main()
