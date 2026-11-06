"""Comparaison complète de deux sorties ; erreurs/absents visibles, tous les coups inclus."""
import argparse
import hashlib
import json
from pathlib import Path


def lire(dossier):
    resume = json.loads((dossier / 'resume.json').read_text())
    niveaux, empreintes, erreurs = {}, {}, []
    for jeu in resume:
        p = dossier / jeu / 'resultat.json'
        if not p.exists():
            erreurs.append(f'{jeu}: resultat absent')
            continue
        for r in json.loads(p.read_text()):
            cle = (jeu, r['niveau'])
            rows = json.loads((dossier / jeu / f"N{r['niveau']}" / 'partie.json').read_text())['rows']
            if len(rows) != r['coups']:
                erreurs.append(f'{cle}: coups incoherents')
            niveaux[cle] = r
            empreintes[cle] = hashlib.sha256(json.dumps([x['action'] for x in rows]).encode()).hexdigest()
            for e in r.get('etapes', []):
                if e.get('raison') == 'exception':
                    erreurs.append(f'{cle}: {e.get("message")}')
    return niveaux, empreintes, erreurs


def comparer(reference, bras):
    ref, hr, er = lire(reference)
    alt, ha, ea = lire(bras)
    gagnes, perdus, lignes, communs = [], [], [], []
    for cle in sorted(ref.keys() | alt.keys()):
        r, a = ref.get(cle, {}), alt.get(cle, {})
        vr, va = bool(r.get('victoire')), bool(a.get('victoire'))
        if va and not vr:
            gagnes.append(cle)
        if vr and not va:
            perdus.append(cle)
        if vr and va:
            communs.append(a['coups'] - r['coups'])
        lignes.append(dict(jeu=cle[0], niveau=cle[1], ref_victoire=vr, bras_victoire=va,
                           ref_coups=r.get('coups'), bras_coups=a.get('coups'),
                           actions_identiques=hr.get(cle) == ha.get(cle)))

    def total(d):
        return dict(niveaux=sum(bool(x['victoire']) for x in d.values()),
                    coups=sum(x['coups'] for x in d.values()), resets=sum(x['resets'] for x in d.values()))

    return dict(reference=str(reference), bras=str(bras), total_reference=total(ref), total_bras=total(alt),
                gagnes=gagnes, perdus=perdus, erreurs=er + ea,
                coups_delta_sur_victoires_communes=sum(communs),
                toutes_actions_identiques=hr == ha, niveaux=lignes)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('reference', type=Path)
    ap.add_argument('bras', type=Path)
    ap.add_argument('sortie', type=Path)
    a = ap.parse_args()
    d = comparer(a.reference, a.bras)
    a.sortie.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in d.items() if k != 'niveaux'}, ensure_ascii=False))
