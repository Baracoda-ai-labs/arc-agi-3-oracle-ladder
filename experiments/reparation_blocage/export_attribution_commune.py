"""Preuves d'actions du contrôleur autonome ; ne reconstruit pas une référence P1.

Seuls les coups reliés à une décision archivée ou au préfixe explicite --neuf
sont attribués. Une lacune rend l'ensemble non évaluable, jamais zéro perte.
"""
import hashlib
import json
from pathlib import Path


def lire(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def exporter(sortie, lignes, *, interruption=False):
    sortie=Path(sortie);session=sortie/'session';commande=lire(sortie/'commande.json')
    argv=commande.get('argv',[])
    aveugle='--neuf' in argv and not any(x in argv for x in ('--source','--prefixe','--archives-niveaux','--transfert-depuis'))
    preuves=[];manques=[];compteurs={};victoires={}
    def cle(p):
        ns=[int(q.name[1:]) for q in p.parents if q.name.startswith('N') and q.name[1:].isdigit()]
        ts=[int(q.name[10:]) for q in p.parents if q.name.startswith('tentative_') and q.name[10:].isdigit()]
        return (ns[0] if ns else 0,ts[0] if ts else 1)
    for p in sorted(session.rglob('partie.json'),key=cle):
        n,t=cle(p)
        if not n:continue
        data=lire(p)
        if data.get('injected'):manques.append({'trace':str(p),'raison':'etat_injecte'})
        for i,row in enumerate(data.get('rows',[]),1):
            compteurs[n]=compteurs.get(n,0)+1
            d=p.parent/f'decision_coup_{i:05}'/'decision.json'
            # La session N1 place les décisions à la racine, contrairement aux niveaux suivants.
            if not d.exists() and n==1 and t==1:d=session/f'decision_coup_{i:05}'/'decision.json'
            origine=None;preuve={'trace':str(p.relative_to(sortie)),'trace_sha256':sha(p),'row':i}
            if d.exists():
                decision=lire(d)
                if decision.get('actions') and decision['actions'][0]==row.get('action'):
                    origine='decision_controleur_commun';preuve.update(decision=str(d.relative_to(sortie)),decision_sha256=sha(d))
            elif aveugle and n==1 and t==1 and i<=8 and row.get('purpose')=='acquisition_generique' and row.get('action') in (1,2,3,4):
                origine='acquisition_generique_du_controleur'
            elif aveugle and row.get('action')==0 and row.get('purpose')=='retry_explicite_compte':
                origine='reset_explicite_du_pilote'
            if origine is None:
                manques.append({'niveau':n,'tentative':t,'coup':compteurs[n],'raison':'decision_ou_acquisition_non_prouvee'})
                continue
            preuves.append({'type':'moteur','etape':'intervention','niveau':n,'coup':compteurs[n],
                            'action':row['action'],'origine':origine,**preuve})
            if row.get('levels_completed',0)>=n:victoires[n]=True
    if not aveugle:manques.append({'raison':'commande_aveugle_non_prouvee'})
    if interruption:manques.append({'raison':'appel_ou_processus_interrompu'})
    if not preuves:manques.append({'raison':'aucune_action_prouvee'})
    for d in lignes:
        if d.get('coups')!=compteurs.get(d['niveau'],0):manques.append({'niveau':d['niveau'],'raison':'compteur_incoherent'})
    statut='non_evaluable' if manques else 'preuves_actions_completes'
    resultat=[dict(d,gagnant=('moteur' if statut!='non_evaluable' and d.get('victoire') and victoires.get(d['niveau']) else None),
                   attribution=statut) for d in lignes]
    meta={'type':'meta','schema':'controleur_commun_v1','attribution_cf2a1f81':statut,
          'regle_imputation':'cf2a1f81_non_modifiee','equivalence_artefacts_P1':False,
          'portee':'actions_autonomes_toutes_origines_incluant_exploration','manques':manques}
    (sortie/'journal_jeu.jsonl').write_text('\n'.join(json.dumps(x) for x in [meta,*preuves])+'\n')
    (sortie/'attribution.json').write_text(json.dumps(meta,indent=2))
    return resultat,meta


def exiger_evaluable(sorties):
    """À appeler AVANT controle_passages.imputation/critere_gel_458."""
    for sortie in sorties:
        fichiers=list(Path(sortie).glob('*/resultat.json'))
        if not fichiers:raise ValueError('Aucun résultat attribuable : '+str(sortie))
        for p in fichiers:
            preuve=p.parent/'attribution.json'
            if not preuve.exists() or lire(preuve).get('attribution_cf2a1f81')!='preuves_actions_completes':
                raise ValueError('Attribution non évaluable : '+str(p.parent))
