"""Audit du raccord sur snapshot local signé ; aucune action SDK ni recherche de plan."""
import argparse
import copy
import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path
import cloudpickle
import numpy as np
from buts_modele_conserve import candidats, actions_modele
from contexte_export import exporter_contextuel
from chrysalide.arc3.moteur import _candidats_buts
from chrysalide.arc3.logique.theorie import Theorie


def audit(snapshot, sortie):
    debut = time.process_time()
    payload = snapshot.read_bytes()
    meta = json.loads(snapshot.with_suffix('.json').read_text())
    sha = lambda b: hashlib.sha256(b).hexdigest()
    assert sha(payload) == meta['sha256']
    a = cloudpickle.loads(payload)
    assert len(a.actions) == meta['actions'] == 112
    assert sha(np.asarray(a.images[-1], dtype=np.int16).tobytes()) == meta['image_sha256']
    precedents_sha = sha(cloudpickle.dumps(a.precedents))
    assert len(a.precedents) == 4
    nom, source = next(iter(a.chaines.items()))
    signature = source.signature()
    th = copy.deepcopy(source.perception.th_releve)
    ancien = a.theorie_precedente.but
    tr = copy.copy(source.perception.tr)
    tr.etats = list(tr.etats[:len(source.grilles)])
    tr.etats += [tr.etat(g) for g in source.grilles[len(tr.etats):]]
    assert Theorie._vrai(ancien, tr.etats[-1])
    assert ancien not in _candidats_buts(th, tr)
    controles, etat = source.rejouer()
    assert etat is not None
    vus = []
    for but, c in candidats(source, actions_modele(source, [6])):
        vus.append(but)
        if len(but) > 3 and but[:3] == ancien:
            break
    else:
        raise AssertionError('Aucun but étendu généré automatiquement')
    assert replace(c.perception.th_releve, but=None) == replace(th, but=None)
    avant, non1 = exporter_contextuel(source.perception, replace(th, but=None), tr.taille)
    apres, non2 = exporter_contextuel(c.perception, replace(c.perception.th_releve, but=None), tr.taille)
    assert not non1 and not non2 and avant == apres
    assert c.diagnostic_extension_but and c.diagnostic_couverture_but
    assert not c.diagnostic_couverture_but['but_confirme']
    assert not any(Theorie._vrai(but, e) for e in tr.etats)
    assert len(a.precedents) == 4 and sha(cloudpickle.dumps(a.precedents)) == precedents_sha
    assert source.signature() == signature and source.perception.th_releve == th
    assert snapshot.read_bytes() == payload
    d = dict(snapshot=str(snapshot), snapshot_sha256=meta['sha256'], observations=112,
        modele=nom, but_ancien=ancien, ancien_vrai_au112=True,
        ancien_exclu_des_candidats=True, issue_observee=a.issues[-1], but_etendu=but,
        generation_automatique=True, candidats_examines=len(vus),
        dynamique_identique=True, export_hors_but_identique=True,
        precedents_conserves=4, precedents_sha256=precedents_sha,
        source_inchangee=True, cache_source_reutilise=controles.get('cache_verifie', False),
        diagnostics_extension=c.diagnostic_extension_but,
        diagnostic_couverture=c.diagnostic_couverture_but,
        admission=c.rejouer()[0], recherche_plan=False, actions_sdk=0,
        cpu_s=round(time.process_time()-debut, 3))
    sortie.write_text(json.dumps(d, indent=2, default=int))
    print(json.dumps({k:v for k,v in d.items() if k not in
        ('admission','diagnostic_couverture','diagnostics_extension')}, default=int))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--snapshot', type=Path, default=Path(__file__).parent/'runs/agent_portefeuille_ft09.pkl')
    p.add_argument('--sortie', type=Path, default=Path(__file__).with_name('AUDIT_INTEGRATION_BUT_ETENDU.json'))
    args = p.parse_args()
    audit(args.snapshot, args.sortie)
