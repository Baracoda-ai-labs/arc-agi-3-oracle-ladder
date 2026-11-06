"""Transfert prévalidé sur relais persistant ; aucun coup ni réaccès ajouté."""
import argparse
import json
import time
from pathlib import Path
from avancer_agent_relais import charger_agent,sauver_agent,aligner
from session_sdk_observee import demander
from session_chaine_generique import agent_transfere


def transferer(relais,source,sortie):
    sortie=Path(sortie);sortie.mkdir(parents=True,exist_ok=False)
    debut=time.process_time();avant=apres=None;transition_envoyee=False
    bilan={'statut':'prevalidation','source_agent':str(source),'agent_nouveau':str(sortie/'agent.pkl')}
    try:
        ancien=charger_agent(source)
        avant=demander(relais,{'op':'status'})
        aligner(ancien,avant)
        if not avant['niveau_gagne'] or avant['jeu_gagne'] or not avant['termine']:
            raise ValueError('Niveau gagné et jeu non terminé requis')
        nouveau=agent_transfere(ancien,ancien.images[-1],avant['actions_disponibles'])
        if nouveau.actions or len(nouveau.images)!=1 or nouveau.attente is not None:
            raise ValueError('Transfert doit commencer sans action ni décision en attente')
        sauver_agent(nouveau,sortie/'agent.pkl')
        # Vérification juste avant transition ; usage exclusif du relais requis.
        frais=demander(relais,{'op':'status'})
        for cle in ('niveau','coups_reels','image_sha256','niveau_gagne','jeu_gagne','termine','actions_disponibles','initialisations'):
            if frais[cle]!=avant[cle]:raise ValueError('Relais changé pendant prévalidation')
        transition_envoyee=True
        apres=demander(relais,{'op':'next_level'})
        if apres['niveau']!=avant['niveau']+1:
            raise ValueError('Niveau inattendu après transition')
        if apres['coups_reels']!=avant['coups_reels'] or apres['initialisations']!=avant['initialisations']:
            raise ValueError('Coût inattendu de transition')
        aligner(nouveau,apres)
        bilan['statut']='transfert_aligne'
        return apres
    except Exception as exc:
        bilan.update(statut='diagnostic_requis',erreur=repr(exc))
        raise
    finally:
        bilan.update(etat_avant=avant,etat_apres=apres,transition_envoyee=transition_envoyee,
            cpu_controleur=time.process_time()-debut,
            actions_nouvelles=(apres['coups_reels']-avant['coups_reels']) if apres else None,
            initialisations_nouvelles=(apres['initialisations']-avant['initialisations']) if apres else None,
            coups_reacces_nouveaux=(apres['coups_reacces']-avant['coups_reacces']) if apres else None,
            cpu_relais_delta=(apres.get('cpu_relais',0)-avant.get('cpu_relais',0)) if apres else None)
        (sortie/'bilan.json').write_text(json.dumps(bilan,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--relais',type=Path,required=True)
    p.add_argument('--agent',type=Path,required=True)
    p.add_argument('--sortie',type=Path,required=True)
    a=p.parse_args();print(json.dumps(transferer(a.relais,a.agent,a.sortie)))
