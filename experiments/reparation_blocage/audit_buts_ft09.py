"""Audit ponctuel sur le seul préfixe17 archivé ; aucun SDK ni suffixe."""
import copy
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np

from representation_legacy_sans_but import construire, clics_etayes
from buts_modele_conserve import chercher
from chrysalide.arc3.moteur import _candidats_buts


def main():
    racine = Path(__file__).parent
    entree = racine / 'runs/legacy_effet_ft09_1/prefixe.json'
    sortie = racine / 'AUDIT_BUTS_FT09.json'
    if sortie.exists():
        raise FileExistsError(sortie)
    debut = time.monotonic()
    h = json.loads(entree.read_text())
    assert len(h['lots']) == 17 and len(h['grilles']) == 18
    source, admission = construire(h, limite_s=2)
    rapport = {
        'source': str(entree.resolve()),
        'source_sha256': hashlib.sha256(entree.read_bytes()).hexdigest(),
        'prefixe_coups': 17, 'nouveaux_coups_sdk': 0, 'suffixe_lu': False,
        'admis': admission['admis'], 'controle': admission['controle'],
        'but_source': source.perception.th_releve.but,
        'inconnus': admission['inconnus'], 'budget_recherche_secondes': 15,
        'gain_reel': False,
    }
    if admission['admis']:
        actions = [('MOUSE', y, x) for _, x, y in clics_etayes(source)]
        deja = set()
        for image, lot in zip(h['grilles'], h['lots']):
            if np.array_equal(image, h['grilles'][-1]):
                for a in lot['actions']:
                    if a['action'] == 'MOUSE':
                        deja.add(('MOUSE', a['row'], a['col']))
        th_avant = copy.deepcopy(source.perception.th_releve)
        signature = source.signature()
        candidats = _candidats_buts(th_avant, source.perception.tr)
        depart_recherche = time.monotonic()
        trouve, essais = chercher({'prefixe17': source}, actions, secondes=15,
                                  accepter=lambda a: tuple(a) not in deja)
        rapport.update(
            actions_coordonnees=actions, premieres_actions_deja_essayees=len(deja),
            buts_candidats=len(candidats), essais=essais,
            statuts=dict(Counter(e['statut'] for e in essais)),
            recherche_secondes=time.monotonic() - depart_recherche,
            plan_trouve=trouve is not None,
            source_inchangee=source.signature() == signature and source.perception.th_releve == th_avant,
        )
        if trouve is not None:
            th_apres = copy.deepcopy(trouve.perception.th_releve)
            th_apres.but = th_avant.but
            valide, preuve = trouve.verifier_plan(trouve.plan['actions'])
            rapport.update(but=trouve.perception.th_releve.but,
                           plan=trouve.plan['actions'], plan_verifie=valide,
                           preuve=preuve, physique_theorie_conservee=th_apres == th_avant,
                           controle_candidat=trouve.rejouer()[0],
                           conclusion='Plan simule valide, but suppose non confirme dans le jeu')
        else:
            rapport['conclusion'] = ('Aucun clic etaye' if not actions else
                'Aucun but candidat compatible avec le prefixe' if not candidats else
                'Aucun plan retourne dans le budget ; absence de solution non prouvee')
    else:
        rapport['conclusion'] = 'Modele source refuse a admission'
    rapport['duree_totale_secondes'] = time.monotonic() - debut
    sortie.write_text(json.dumps(rapport, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: rapport[k] for k in ('admis', 'conclusion', 'duree_totale_secondes')}))
    print(str(sortie.resolve()))


if __name__ == '__main__':
    main()
