"""Palier CPU après budget épuisé, sans SDK ni nouvelle hypothèse.

Le pilote fournit les échecs signés au moment de la recherche courte :
{nom: {'refus': 'budget', 'signature': signature_recherche(chaine, offre)}}.
Une simple absence de plan (ou espace épuisé) ne déclenche pas ce palier.
"""
import hashlib
import json
import tempfile
import time
from pathlib import Path
from selection_observee import SelectionObservee
from rechercher_selection_portefeuille import rechercher, portefeuille
from avancer_agent_relais import sauver_agent


def signature_recherche(c, offre):
    payload={'chaine':c.signature(),'programme':c.programme,
             'actions':c.actions,'offre':offre}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()


def _workers(agent):
    n=getattr(agent,'recherche_prolongee_workers',2)
    if n not in (1,2):raise ValueError('Un ou deux workers requis')
    return n


def _executer(agent, nom, secondes):
    # Réutiliser le travailleur vérifié, sur snapshot isolé et empreinté.
    with tempfile.TemporaryDirectory(prefix='chrysalide-recherche-') as dossier:
        path=Path(dossier)/'agent.pkl'
        sauver_agent(agent,path)
        if _workers(agent)==1:
            # Le poids 3 vient déjà d'épuiser son budget dans le chercheur normal.
            return [rechercher((str(path),nom,10,secondes))]
        c=agent.chaines[nom];signature=signature_recherche(c,[])
        def valider(plan):
            return agent.chaines.get(nom) is c and not c.refute and signature_recherche(c,[])==signature and c.verifier_plan(plan)[0]
        return portefeuille([(str(path),nom,p,secondes) for p in (3,10)],valider)


def prolonger(agent, offre, echecs, secondes=120):
    """Un candidat et un palier par appel ; retourne un statut, jamais une action SDK."""
    if secondes<=0:raise ValueError('Budget de calcul positif requis')
    if any(c.plan and not c.refute for c in agent.chaines.values()):
        return {'statut':'plan_deja_present'}
    workers=_workers(agent)
    memoire=getattr(agent,'recherches_prolongees',{})
    for nom,c in agent.chaines.items():
        if not isinstance(c.perception,SelectionObservee) or c.refute:continue
        sig=signature_recherche(c,offre)
        echec=echecs.get(nom,{})
        if echec.get('refus')!='budget' or echec.get('signature')!=sig:continue
        if sig in memoire:continue
        controle,etat=c.rejouer()
        if etat is None or not all(controle.get(k) for k in
                ('catalogue_shacl','traduction_python','rejeu','compilation_fidele')):continue
        agent.recherches_prolongees=memoire
        memoire[sig]={'statut':'en_cours','modele':nom,'budget_s_par_worker':secondes}
        debut=time.monotonic();cpu=time.process_time()
        rec={'type':'recherche_selection_prolongee','modele':nom,'signature':sig,
             'budget_s_par_worker':secondes,'poids':[10] if workers==1 else [3,10],'workers':workers,'sdk_actions':0}
        try:
            resultats=_executer(agent,nom,secondes)
            rec['cpu_recherches_s']=sum(r['cpu_s'] for r in resultats)
            rec['cpu_enfants_s']=sum(r.get('cpu_enfants_recoltes_s',0) for r in resultats) if any('cpu_enfants_recoltes_s' in r for r in resultats) else (rec['cpu_recherches_s'] if workers==2 else 0)
            rec['recherches']=[{k:r.get(k) for k in ('poids','preuve','cpu_s','rss_pic','premier_plan_valide','enfants_termines','annulation_join_s','cpu_incomplet','cpu_enfants_recoltes_s')} |
                {'longueur':len(r['plan']) if r.get('plan') is not None else None} for r in resultats]
            courant=agent.chaines.get(nom)
            if courant is not c or c.refute or signature_recherche(c,offre)!=sig:
                rec['statut']='resultat_perime'
            else:
                rec['statut']='aucun_plan_valide'
                for r in (r for r in resultats if r.get('plan')):
                    if not c.verifier_plan(r['plan'])[0]:continue
                    adoption=c.adopter_plan(r['plan'],origine='portefeuille_selection_cpu_autonome')
                    if adoption.get('statut')=='plan_simule_valide':
                        rec.update(statut='plan_simule_valide',poids_retenu=r['poids'],longueur=len(r['plan']))
                        break
        except Exception as exc:
            rec.update(statut='erreur_recherche',erreur=repr(exc))
        finally:
            rec.update(mur_s=time.monotonic()-debut,cpu_parent_s=time.process_time()-cpu)
            rec['cpu_total_s']=rec['cpu_parent_s']+rec.get('cpu_enfants_s',0)
            rec['cpu_complet']= 'cpu_enfants_s' in rec and not any(r.get('cpu_incomplet') for r in resultats)
            memoire[sig]=dict(rec);agent.journal.append(rec)
        return rec
    return {'statut':'aucun_palier_eligible'}
