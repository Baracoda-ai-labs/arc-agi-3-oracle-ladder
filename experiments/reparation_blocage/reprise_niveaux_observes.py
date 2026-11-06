"""Reprise depuis épisodes observés : mémoire apprise, tous accès comptés par SDK."""
import copy
import json
from pathlib import Path
import numpy as np
from chaine_agent_integree import lots
from chaine_coherente import Chaine
from chrysalide.arc3.moteur import MoteurC


def preparer(source, exiger_plan=True):
    from session_chaine_generique import nouvel_agent
    meta=json.loads((source/'etat.json').read_text())
    n=meta['niveau']; episodes=[]; precedents=[]; prior=None; journal=[]
    for niveau in range(1,n+1):
        p=source/f'N{niveau}'/'partie'
        z=np.load(p.with_suffix('.npz'))
        rows=json.loads(p.with_suffix('.json').read_text())['rows']
        gs=z['images'].tolist(); ls=lots([r['action'] for r in rows])
        if niveau<n and rows[-1]['levels_completed']<niveau:
            raise ValueError('Niveau précédent sans victoire réelle')
        gagne = rows[-1]['levels_completed'] >= niveau if rows else False
        h=dict(grilles=gs[:-1] if gagne else gs,lots=ls[:-1] if gagne else ls,precedents=precedents)
        m=MoteurC(budget=15,limite_plan=100000,theorie_precedente=prior)
        proposition=m.proposer(h)
        journal.append({'niveau':niveau,'infos':copy.deepcopy(m.infos),'plan':proposition[0] if proposition else None})
        episodes.append((z,rows))
        if gagne:
            c = None
            if proposition:
                c=Chaine(m,proposition[1],h['grilles'],h['lots'],[],coups_deja_joues=len(h['lots']))
                finale=Chaine.action_tuple(ls[-1]['actions'][0])
                if c.rejouer()[1] is None or not c.verifier_plan([finale])[0]:
                    raise ValueError('Mémoire précédente non vérifiée')
                prior=copy.deepcopy(getattr(m,'th_plan',None) or m.th_releve)
            if niveau==n:
                if c is None:raise ValueError('Victoire sans modèle reconstruit')
                a=nouvel_agent(z['images'],[r['action'] for r in rows],
                    [z[f'film_{i+1}'] for i in range(len(rows))],['continue']*(len(rows)-1)+['niveau'])
                a.precedents=copy.deepcopy(precedents);a.modele_gagnant=c
                a.reconstruction=False;a.journal.append({'type':'reprise_victoire','niveaux':journal})
            precedents.append(dict(grilles=gs[:-1],lots=ls[:-1],finale=ls[-1]))
        else:
            a=nouvel_agent(z['images'],[r['action'] for r in rows],
                [z[f'film_{i+1}'] for i in range(len(rows))],['continue']*len(rows))
            a.precedents=precedents;a.theorie_precedente=prior
            a.reconstruction=False
            if proposition is None:
                if exiger_plan:raise ValueError('Reprise sans nouvelle proposition')
                a.reconstruction=True
                a.journal.append({'type':'reprise_a_diagnostiquer','source':str(source),'niveaux':journal})
                continue
            c=a._chaine(m,proposition[1])
            plan=[Chaine.action_tuple(x) for x in proposition[0]]
            if c.rejouer()[1] is None or c.adopter_plan(plan)['statut']!='plan_simule_valide':
                raise ValueError('Plan de reprise non admissible')
            a.chaines={'p1_but_hypothese':c};a.releves_p1={len(rows)//8}
            a.journal.append({'type':'reprise_observee','source':str(source),'niveaux':journal})
    return a,episodes,meta
