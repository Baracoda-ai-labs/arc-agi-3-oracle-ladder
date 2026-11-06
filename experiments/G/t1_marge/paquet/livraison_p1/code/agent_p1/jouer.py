"""Agent intégré figé P1 : un passage depuis RESET par jeu, budget par niveau, mémoire inter-niveaux et inter-jeux.

Routage par niveau (aucun nom de jeu utilisé) :
 1. structure « pièces poussées + cibles » reconnue par la perception v4 (PousseeGenerale) → agent v4 poussée ;
 2. sinon, sonde de déplacement (≤ 4 coups, comptés) : translation rigide d'un contrôlé sur grille avec but ponctuel
    (perception v4 g50t) → v4 + inventeur (la v4 joue, l'inventeur prend la main sur contradiction) ;
 3. toujours ensuite, s'il reste du budget et que le niveau n'est pas gagné : exploration générique (jamais d'abstention).
Usage : python -m agent_p1.jouer --jeux <dossier_jeux> --sortie <dossier> [--jeu ar25 ...] [--memoire <dossier>] [--budget 150]
"""
import argparse, json, sys, time, traceback
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / 'references/astra4/livraison_astra4/ajouts'))
sys.path.insert(0, str(RACINE))

from . import bornes  # noqa: E402
bornes.activer()
from .labo import LaboP1  # noqa: E402
from .journal import Journal, sha_code  # noqa: E402
from .generique import Explorateur, Memoire  # noqa: E402


def lister_jeux(dossier):
    return sorted(p.parent.parent.name for p in Path(dossier).glob('*/*/metadata.json'))


def charger_memoire(d):
    p = Path(d) / 'memoire_actions.json'
    return Memoire(json.loads(p.read_text()) if p.exists() else {})


def sauver_memoire(d, mem):
    Path(d).mkdir(parents=True, exist_ok=True)
    (Path(d) / 'memoire_actions.json').write_text(json.dumps(mem.d, indent=0))


def essai_poussee(lab, out, budget, j):
    try:
        from boucle_v4.poussee_generale import PousseeGenerale
        m = PousseeGenerale(lab.image)
        if not getattr(m, 'targets', None):
            return None
    except Exception as e:
        return None
    from boucle_v4.agent_poussee import run as prun
    j.ecrire('routage', step=len(lab.rows), choix='v4_poussee', cibles=len(m.targets))
    r = prun(lab.level, None, out / 'v4_poussee', budget, 10 ** 9, lab=lab)
    return dict(agent='v4_poussee', victoire=r['victory'], raison=r['reason'])


def essai_fantome(lab, out, budget, j, biblio):
    """v4 g50t + inventeur. La v4 identifie elle-même le contrôlé (≤ 4 coups) ; si sa perception ne trouve ni contrôlé ni
    but ponctuel, elle est arrêtée aussitôt et la main passe à l'exploration générique."""
    dispo = lab.actions_disponibles or []
    if not all(a in dispo for a in (1, 2, 3, 4)):
        return None
    from .agent import Agent
    j.ecrire('routage', step=len(lab.rows), choix='v4_inventeur_essai')
    ag = Agent(lab.game, lab.level, None, out / 'inventeur', 'complet', budget, 10 ** 9, biblio, lab=lab)
    r = ag.run()
    return dict(agent='v4_inventeur', victoire=r['victoire'], raison=r['raison'],
                hypotheses=r['hypotheses_generees'], mecanismes=r['mecanismes'],
                defauts_ARC=r.get('defauts_ARC'), biblio=r.get('mecanismes_biblio_utilises'))


def jouer_jeu(dossier, jeu, sortie, budget=150, memoire=None, max_niveaux=20, graine=0):
    out = Path(sortie) / jeu; out.mkdir(parents=True, exist_ok=True)
    memdir = Path(memoire) if memoire else out / 'memoire'
    mem = charger_memoire(memdir); mem.changer_jeu(jeu); biblio = memdir / 'bibliotheque.json'
    j = Journal(out, 'journal_jeu', dict(jeu=jeu, dossier=str(dossier), budget=budget, memoire=str(memdir),
                                         code=sha_code(), graine=graine))
    lab = LaboP1(jeu, 1, dossier, out / 'N1' / 'partie'); res = []
    for niveau in range(1, max_niveaux + 1):
        t0 = time.monotonic(); od = out / f'N{niveau}'; etapes = []
        def phase(nom, f):
            try:
                r = f()
                if r:
                    etapes.append(r)
            except Exception as e:      # une phase qui plante n'arrête jamais le niveau
                etapes.append(dict(agent=nom, victoire=False, raison='exception', message=str(e),
                                   tb=traceback.format_exc()[-1200:]))
        phase('v4_poussee', lambda: essai_poussee(lab, od, budget, j))
        if not lab.won and len(lab.rows) < budget and not getattr(lab, 'partie_gagnee', False):
            if lab.finished:
                lab.reset_apres_defaite()
            phase('v4_inventeur', lambda: essai_fantome(lab, od, budget, j, biblio))
        tentative = 0
        while not lab.won and len(lab.rows) < budget and tentative < 3:
            tentative += 1
            def gen():
                if lab.finished and not lab.won:
                    lab.reset_apres_defaite()
                ex = Explorateur(lab, j, mem, graine + tentative)
                j.ecrire('routage', step=len(lab.rows), choix='generique', tentative=tentative)
                raison = ex.jouer(budget)
                return dict(agent='moteur' if raison == 'victoire_moteur' else 'generique', victoire=lab.won, raison=raison,
                            etats=len(ex.aretes), moteur_a_joue=getattr(ex, 't1_coups', 0))  # C (T1) : attribution
            phase('generique', gen)
        ligne = dict(jeu=jeu, niveau=niveau, victoire=lab.won, coups=len(lab.rows), resets=lab.resets,
                     defaites=lab.defaites, secondes=round(time.monotonic() - t0, 1), etapes=etapes,
                     gagnant=next((e['agent'] for e in etapes if e.get('victoire')), None))
        res.append(ligne); j.ecrire('niveau', **ligne)
        (out / 'resultat.json').write_text(json.dumps(res, indent=1, default=str, ensure_ascii=False))
        sauver_memoire(memdir, mem)
        print(json.dumps({k: ligne[k] for k in ('jeu', 'niveau', 'victoire', 'coups', 'gagnant')}), flush=True)
        if not lab.won or getattr(lab, 'partie_gagnee', False):
            break
        lab = lab.next_level(out / f'N{niveau + 1}' / 'partie')
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jeux', required=True); ap.add_argument('--sortie', required=True)
    ap.add_argument('--jeu', nargs='*'); ap.add_argument('--memoire'); ap.add_argument('--budget', type=int, default=150)
    ap.add_argument('--memoire_depart', help='dossier figé copié au départ (bibliothèque + a priori), jamais modifié')
    a = ap.parse_args()
    jeux = a.jeu or lister_jeux(a.jeux)
    memoire = a.memoire or str(Path(a.sortie) / 'memoire_inter_jeux')
    if a.memoire_depart:
        import shutil
        Path(memoire).mkdir(parents=True, exist_ok=True)
        for f in Path(a.memoire_depart).glob('*.json'):
            if not (Path(memoire) / f.name).exists():
                shutil.copy(f, Path(memoire) / f.name)
    tout = {}
    for g in jeux:
        tout[g] = jouer_jeu(a.jeux, g, a.sortie, a.budget, memoire)
    Path(a.sortie, 'resume.json').write_text(json.dumps(
        {g: dict(niveaux_gagnes=sum(x['victoire'] for x in r), coups=sum(x['coups'] for x in r)) for g, r in tout.items()},
        indent=1))


if __name__ == '__main__':
    main()
