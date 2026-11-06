"""Préflight sans SDK : préfixe causal configurable, jamais de contrefactuel rejoué.

Réutilise depuis_trace/installeur mémoire et l'entrée agent courante. Le suffixe
réservé de l'ancien audit n'est ni consulté ni réutilisé pour induire une règle.
"""
import argparse
import hashlib
import json
import pickle
import subprocess
import time
from pathlib import Path

import numpy as np
from boucle_agent_integree import empreintes
from preparer_modele_transfert import depuis_trace
from session_chaine_generique import nouvel_agent

R = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(args):
    args.sortie.mkdir(parents=True, exist_ok=False)
    source = R / 'runs/routage_arc1/reel/N1/partie'
    trace = R / 'runs/transfert_modele_commun_ar25_1/N2/partie'
    precedent = R / 'AUDIT_CONTEXTE_TRANSFERT.json'
    hashes = empreintes()
    hashes[str(Path(__file__).resolve())] = sha(Path(__file__))
    debut, cpu = time.monotonic(), time.process_time()
    rapport = dict(statut='preflight_en_cours', SDK=False, nouvelles_actions_reelles=0,
        victoire_nouvelle=False, observations_accessibles=list(range(1,args.observations+1)), suffixe_utilise=False,
        entree='session_chaine_generique.nouvel_agent puis installer_modele_jeu',
        offre=[1,2,3,4,5], offre_provenance='protocole_transfert_archive_pas_offre_SDK_revalidee',
        graine_exploration=0, secondes_par_decision=args.secondes,
        source_N1=str(source), trace_N2=str(trace), source_sha256=sha(source.with_suffix('.npz')),
        trace_sha256=sha(trace.with_suffix('.npz')), audit_ancien_sha256=sha(precedent),
        commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(), decisions=[])
    def sauver():
        rapport.update(cpu_s=time.process_time()-cpu, mur_s=time.monotonic()-debut,
                       sources_inchangees=empreintes(hashes)==hashes)
        (args.sortie/'rapport.json').write_text(json.dumps(rapport, ensure_ascii=False,
            indent=2, default=lambda x: x.item() if hasattr(x,'item') else str(x)))
        (args.sortie/'sources.json').write_text(json.dumps(hashes, indent=2))
    try:
        # Découpage avant toute construction de contrôleur ; pas d'image future injectée.
        with np.load(trace.with_suffix('.npz')) as z:
            images=z['images'][:args.observations+1].copy()
            films=[z[f'film_{i+1}'].copy() for i in range(args.observations)]
        rows=json.loads(trace.with_suffix('.json').read_text())['rows'][:args.observations]
        ancien=json.loads(precedent.read_text())
        rapport['ancien_audit_decisions']=ancien['decisions']
        modele,*_=depuis_trace(source,[1,2,3,4,5])
        memoire_avant=pickle.dumps(modele)
        a=nouvel_agent([images[0]],[],[],[],graine_exploration=0)
        a.installer_modele_jeu(modele)
        rapport['modeles_initialement_admis']=list(a.chaines)
        for i in range(args.observations):
            d=a.decider([1,2,3,4,5],secondes=args.secondes)
            rec={'coup':i+1,'decision':d,'action_archivee':rows[i]['action'],
                 'modeles_avant_observation':list(a.chaines)}
            rapport['decisions'].append(rec)
            # Une décision nouvelle n'autorise pas à lui fournir l'effet d'une autre action.
            if d.get('actions') != [rows[i]['action']]:
                rapport['statut']='decision_differente_effet_non_observe'
                break
            rec['observation']=a.observer(d['actions'][0],images[i+1],films[i],'continue',source='trace')
            rec['diagnostic_transfert']=a.diagnostic_transfert
            rec['modeles_apres_observation']=list(a.chaines)
            rec['memoire_source_inchangee']=memoire_avant==pickle.dumps(modele)
            rec['historique_controleur']=len(a.actions)
        else:
            rapport['statut']='prefixe_causal_traite'
        rapport['memoire_source_inchangee']=memoire_avant==pickle.dumps(modele)
        rapport['modeles_finaux']=list(a.chaines)
        rapport['debut_contexte']=a.debut_contexte
        rapport['gain_vs_ancien_audit_non_prouve']=True
        observations = sum('observation' in r for r in rapport['decisions'])
        rapport['observations_effectivement_traitees'] = observations
        # La conservation avant observer n'établit pas la conservation après contradiction.
        sequence_observee = observations >= 2
        rapport['statut_criteres_observation'] = ('teste_sur_deux_observations'
            if sequence_observee else 'non_teste_sequence_incomplete')
        rapport['criteres_nouveaute']={
            'perte_globale_ancienne_evitee': (bool(a.chaines) and rapport['memoire_source_inchangee'])
                if sequence_observee else None,
            'sans_rejeu_ancien_prefixe_invalide': (a.debut_contexte==2) if sequence_observee else None,
            'action_changee_vs_audit_ancien':any(
                r['decision'].get('actions') != [v['action']]
                for r,v in zip(rapport['decisions'],ancien['decisions'])),
            'nouveau_SDK_interdit_si_seule_reproduction_ancien_audit':True}
        (args.sortie/'journal_controleur.json').write_text(json.dumps(a.journal,
            ensure_ascii=False,indent=2,default=str))
    except Exception as exc:
        rapport.update(statut='erreur_preflight',erreur=repr(exc))
        raise
    finally:
        sauver()
    print(json.dumps({k:rapport[k] for k in ('statut','cpu_s','sources_inchangees','criteres_nouveaute') if k in rapport}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sortie',type=Path,required=True)
    p.add_argument('--secondes',type=float,default=3.)
    p.add_argument('--observations',type=int,choices=range(2,57),default=2)
    main(p.parse_args())
