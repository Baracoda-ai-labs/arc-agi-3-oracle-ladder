"""Audit de nouvelles hypothèses terminales sur traces, sans SDK ni recherche."""
import argparse
import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path
from avancer_agent_relais import charger_agent
from extension_but_relationnel import proposer
from diagnostic_couverture_but import diagnostiquer
from buts_modele_conserve import candidats, actions_modele
from chrysalide.arc3.logique.theorie import Theorie, motif_ecarts
from chrysalide.arc3.moteur import _candidats_buts
import copy


def auditer(snapshot, sortie, offre):
    debut=time.process_time()
    payload=snapshot.read_bytes()
    a=charger_agent(snapshot)
    source=next(c for c in a.chaines.values() if not c.refute and hasattr(c.perception,'th_releve'))
    th=source.perception.th_releve
    signature=source.signature()
    tr=copy.copy(source.perception.tr)
    tr.etats=[tr.etat(g) for g in source.grilles]
    extensions,preuves=proposer(th,tr,source.grilles)
    filtres=_candidats_buts(replace(th,buts_motifs=[*th.buts_motifs,*extensions]),tr)
    lignes=[]
    for but,preuve in zip(extensions,preuves):
        vrais=[i for i,e in enumerate(tr.etats) if Theorie._vrai(but,e)]
        lignes.append({'but':but,'role':preuve['role_propose'],
            'vrai_sur_observations_aux_indices':vrais,
            'candidat_conserve':but in filtres,
            'ecarts_par_observation':[motif_ecarts(e,*but[1:]) for e in tr.etats],
            'but_confirme':False})
    restants={b for b in extensions if b in filtres}
    admissions=[]
    # Offre explicite du journal observé ; aucune action envoyée au jeu.
    for but,c in (candidats(source,actions_modele(source,offre)) if restants else ()):
        if but not in restants:continue
        assert replace(c.perception.th_releve,but=None)==replace(th,but=None)
        admissions.append({'but':but,'role':next(p['role_propose'] for p in preuves if p['candidat']==but),
            'controle':c.rejouer()[0], 'dynamique_identique':True})
        restants.remove(but)
        if not restants:break
    assert not restants
    assert source.signature()==signature and snapshot.read_bytes()==payload
    rapport={'snapshot':str(snapshot),'sha256':hashlib.sha256(payload).hexdigest(),
        'observations':len(a.actions),'source':source.signature(),
        'hypotheses':lignes,'admissions':admissions,
        'couverture':diagnostiquer(th,tr,source.grilles),
        'actions_sdk':0,'offre_auditee':offre,'victoire_nouvelle':False,'cpu_s':time.process_time()-debut,
        'limite':'Diagnostic retrospectif sur traces de developpement, pas validation prospective ni preuve du but.'}
    with sortie.open('x') as f:json.dump(rapport,f,indent=2,default=int)
    print(json.dumps({'observations':len(a.actions),'roles_admis':[x['role'] for x in admissions],
        'sdk':0,'cpu_s':rapport['cpu_s']}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--sortie',type=Path,required=True)
    p.add_argument('--actions',type=int,nargs='+',required=True)
    args=p.parse_args();auditer(args.snapshot,args.sortie,args.actions)
