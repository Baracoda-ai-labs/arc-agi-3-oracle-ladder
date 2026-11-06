"""Extraire les révisions et leur validation ultérieure, sans inventer de vérité."""
import hashlib
import json

def extraire(journal):
    pending=[];lecons=[]
    for evenement in journal:
        if evenement['type'] in ('revision_solidite','revision_regle'):
            pending.append(evenement)
        if evenement['type']!='observation':continue
        coup=evenement['coup']
        # Résultats postérieurs séparés de l'information disponible pour la révision.
        for lecon in lecons:
            for r in evenement['resultats']:
                if r['nom']==lecon['modele_apres']:
                    lecon['validation_ulterieure'].append({
                        'coup':coup,'statut':r['statut'],
                        'pixels_ecart':r.get('pixels_ecart'),
                        'source':r.get('source')})
        for e in pending:
            for patch in e.get('patches_admis',[]):
                rev=patch['revision']
                nom=e['depuis']+'/'+rev['operateur']+'_'+str(rev['classe'])
                entree={'coup_disponible':coup,'programme_avant':e['programme_avant'],
                        'contre_exemple':[r for r in evenement['resultats'] if r['nom']==e['depuis']],
                        'modele_avant':e['depuis']}
                cible={'revision':rev,'programme_apres':patch['programme_apres'],
                       'statut':'compatible_prefixe_observe','regle_transjeu_prouvee':False,
                       'action_optimale':None}
                ident=hashlib.sha256(json.dumps([entree,cible],sort_keys=True).encode()).hexdigest()
                lecons.append({'id':ident,'entree':entree,'cible':cible,
                    'modele_apres':nom,'validation_ulterieure':[],
                    'usage':'proposition_revision_conditionnelle',
                    'essais_candidats':e['essais']})
        pending=[]
    return lecons
