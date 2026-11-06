"""Essai préinscrit : ancien énumérateur, puis un seul patch multimodal sur une trace ARC."""
import ast
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path[:0] = [str(ICI / 'paquet'), str(ICI / 'paquet/livraison_p1/code')]

import banc_chaine
from chaine_coherente import Chaine
from client_multimodal import generer

from chrysalide.arc3.logique.faits import Trajectoire
from chrysalide.arc3.logique.menu_mecanismes import MENU, enumerer
from chrysalide.arc3.moteur import _codes_c, _exporter, nom_action
from chrysalide.langue import vers_python
from chrysalide.qwen.images import images_coup


def texte_patch(avant, apres):
    a = {k: v for k, v in avant.items() if k != 'regles'}
    b = {k: v for k, v in apres.items() if k != 'regles'}
    if a != b:
        raise ValueError('Modification hors des regles : Patch non applicable')
    aa = {r['nom']: r for r in avant['regles']}
    bb = {r['nom']: r for r in apres['regles']}
    retire = [nom for nom, r in aa.items() if bb.get(nom) != r]
    ajoute = [r for nom, r in bb.items() if aa.get(nom) != r]
    source = vers_python({'regles': ajoute})
    valeur = ast.parse(source).body[-1].value
    regles = next(k.value for k in valeur.keywords if k.arg == 'regles')
    return f'REPONSE = Reponse(patch=Patch(retire={retire!r}, ajoute={ast.unparse(regles)}))'


def main():
    sortie = ICI / 'reparation_arc_multimodale'
    sortie.mkdir(exist_ok=False)
    captures = []
    original = banc_chaine.Chaine

    class Capture(Chaine):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captures.append(self)

    banc_chaine.Chaine = Capture
    try:
        reference = banc_chaine.un_cas('arc_blocage_terminale_g1', 'm0r0', 2, 120)
    finally:
        banc_chaine.Chaine = original
    c = captures[-1]
    assert c.refute and c.contre_exemples[-1]['statut'] == 'modele_refute'
    assert reference['observations'][-1]['pixels_ecart'] == 8
    m = c.perception
    tr = Trajectoire(c.grilles, _codes_c(c.lots), atomiques=m.tr.atomiques,
                     ech=(m.tr.s, m.tr.ox, m.tr.oy), exclues_heritees=m.tr.exclues)
    sources = [(tr, None, None)]
    assert len(MENU) <= 15
    t0 = time.process_time()
    propositions = enumerer(m.th_plan, sources, tr, limite_s=1)
    bilan = {'nouveaux_appels_sdk': 0, 'appels_ia': 0, 'enumeration_cpu_s': time.process_time() - t0,
             'enumeration': [], 'admissible': False, 'victoire_reelle_supplementaire': False}
    (sortie / 'reference.json').write_text(json.dumps(reference, ensure_ascii=False, indent=2, default=repr))
    for prop in propositions:
        p, non = _exporter(prop['theorie'], tr.taille)
        ligne = {k: v for k, v in prop.items() if k != 'theorie'}
        try:
            if non:
                raise ValueError(f'Non exporte : {non}')
            patch = texte_patch(c.programme, p)
            candidat = copy.deepcopy(c)
            ligne['verification'] = candidat.patch(patch)
            if ligne['verification']['statut'] == 'patch_valide_sur_observations':
                c = candidat
                bilan['admissible'] = True
                bilan['source_correction'] = 'enumeration_existante'
        except (ValueError, TypeError, KeyError) as e:
            ligne['refus'] = str(e)
        bilan['enumeration'].append(ligne)
        if bilan['admissible']:
            break
    (sortie / 'enumeration.json').write_text(json.dumps(bilan, ensure_ascii=False, indent=2, default=repr))
    if not bilan['admissible']:
        dossier = c.dossier_ia()
        (sortie / 'dossier.json').write_text(json.dumps(dossier, ensure_ascii=False, indent=2, default=repr))
        pages = c.films.planches(-1)
        initiale = Chaine(m, c.programme, c.grilles[:-1], c.lots[:-1], c.actions,
                         coups_deja_joues=c.coups - 1)
        _, courant = initiale.rejouer()
        assert courant is not None
        pc, sc = courant
        pc.step(sc, nom_action(c.lots[-1]['actions'][0]))
        comparaison = images_coup(m.vue(c.grilles[-2]), m.vue(c.grilles[-1]), m.rendu(sc))[1]
        pages.append(comparaison)
        for i, page in enumerate(pages):
            (sortie / f'image_{i}.png').write_bytes(page)
        bilan['appels_ia'] = 1
        try:
            r = c.demander_patch(generer, enumeration_infructueuse=True, images=pages, contexte=32768)
            (sortie / 'reponse.txt').write_text(r['reponse_brute'])
            bilan['ia'] = {k: v for k, v in r.items() if k != 'reponse_brute'}
            bilan['admissible'] = r['statut'] == 'patch_valide_sur_observations'
            if bilan['admissible']:
                bilan['source_correction'] = '27b_multimodal'
        except (ValueError, TypeError, KeyError, SyntaxError, RuntimeError, OSError) as e:
            bilan['ia'] = {'statut': 'erreur_transport_ou_generation', 'erreur': repr(e)}
    if bilan['admissible']:
        base = ICI / 'runs/arc_blocage_terminale_g1/m0r0/N2'
        images = np.load(base / 'partie.npz')['images']
        rows = json.loads((base / 'partie.json').read_text())['rows']
        from agent_p1.releve_moteur import _lot
        controle = Chaine(m, c.programme, [g.tolist() for g in images[80:131]],
                          [_lot(r['action']) for r in rows[80:130]], c.actions, coups_deja_joues=130)
        bilan['observations_supplementaires'] = controle.rejouer()[0]
        bilan['replanification'] = c.proposer(secondes=2)
    (sortie / 'bilan.json').write_text(json.dumps(bilan, ensure_ascii=False, indent=2, default=repr) + '\n')
    print(json.dumps(bilan, ensure_ascii=False, default=repr))


if __name__ == '__main__':
    main()
