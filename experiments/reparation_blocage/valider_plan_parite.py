"""Admet un plan archivé et vérifie six prédictions, sans action réelle."""
import copy, hashlib, json, time
from dataclasses import replace
from pathlib import Path
import cloudpickle
import numpy as np
from buts_modele_conserve import candidats, actions_modele
from extension_but_relationnel import proposer
from contexte_export import exporter_contextuel
from chaine_coherente import Chaine
from chrysalide.arc3.moteur import _lot_c
from chrysalide.arc3.logique.theorie import Theorie
from chrysalide.arc3.langage import Programme
from chrysalide.arc3.sim_rapide import ProgrammeCompile
from chrysalide.arc3.logique.plan_langage import cle_complete


def valider(root):
    debut=time.process_time();snapshot=root/'runs/agent_portefeuille_ft09.pkl'
    payload=snapshot.read_bytes();sha=hashlib.sha256(payload).hexdigest()
    meta=json.loads(snapshot.with_suffix('.json').read_text())
    entree=root/'AUDIT_PARITE2_SNAPSHOT112_25-10.json';audit=json.loads(entree.read_text())
    assert sha==meta['sha256']==audit['snapshot_sha256']
    a=cloudpickle.loads(payload);assert len(a.actions)==112
    assert hashlib.sha256(np.asarray(a.images[-1],dtype=np.int16).tobytes()).hexdigest()==meta['image_sha256']
    source=next(iter(a.chaines.values()));prior=a.theorie_precedente.but
    choix=next(e for e in audit['essais'] if tuple(e['but'][:3])==prior and len(e['but'])>3 and e['plan_theorie'])
    but=choix['but']
    c=next(c for b,c in candidats(source,actions_modele(source,[6])) if json.loads(json.dumps(b))==but)
    tr=c.perception.tr;codes=[tuple(x) for x in choix['plan_theorie']]
    plan=[Chaine.action_tuple(_lot_c(x,tr)) for x in codes]
    adoption=c.adopter_plan(plan,origine='parite_generique_archivee')
    assert adoption['statut']=='plan_simule_valide',adoption
    th=source.perception.th_releve
    buts,_=proposer(th,tr,source.grilles);assert len(buts)==6
    _,(pc0,sc0)=source.rejouer()
    executants=[]
    for b in buts:
        texte,non=exporter_contextuel(source.perception,replace(th,but=b),tr.taille);assert not non
        pi,pc=Programme(texte),ProgrammeCompile(texte)
        pi.etat=copy.deepcopy(pc0.etat);pc.etat=copy.deepcopy(pc0.etat);pc._ref.etat=pc.etat
        executants.append((pi,pc,copy.deepcopy(sc0),copy.deepcopy(sc0)))
    monde=tr.etat(a.images[-1]);physique=replace(th,but=None);predictions=[]
    for k,(code,action) in enumerate(zip(codes,plan),1):
        monde,_=physique.pas(monde,code,tr.taille);vrais=[]
        image_theorie=physique.rendu(monde,tr.taille,tr.fond)
        for j,(b,(pi,pc,si,sc)) in enumerate(zip(buts,executants)):
            si.issue=sc.issue=None
            pi.step(si,action);pc.step(sc,action)
            assert cle_complete(si,pi.etat)==cle_complete(sc,pc.etat)
            image=source.perception.rendu(sc)
            assert np.array_equal(image,source.perception._masquer(image_theorie))
            vrai=Theorie._vrai(b,monde)
            assert (sc.issue in ('niveau','victoire'))==vrai
            if vrai:vrais.append(j)
        predictions.append({'pas':k,'action':action,'buts_vrais':vrais,
            'buts_faux':[j for j in range(len(buts)) if j not in vrais],
            'image_sha256':hashlib.sha256(np.asarray(image,dtype=np.int16).tobytes()).hexdigest()})
    assert 0<len(predictions[-1]['buts_vrais'])<len(buts)
    assert snapshot.read_bytes()==payload
    resultat={'snapshot_sha256':sha,'source_rapport_sha256':hashlib.sha256(entree.read_bytes()).hexdigest(),
        'observations':112,'but_herite':prior,'but_selectionne':but,'plan':plan,'longueur':len(plan),
        'adoption':adoption,'buts':buts,'predictions':predictions,
        'premier_desaccord_terminal':next(p['pas'] for p in predictions if p['buts_vrais']),
        'theorie_interprete_compile_identiques':True,'snapshot_inchange':True,
        'cpu_s':time.process_time()-debut,'actions_sdk':0,'victoire_reelle':False,
        'sources_sha256':{str(Path(__file__).name):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
    (root/'AUDIT_VALIDATION_PLAN_PARITE_112.json').write_text(json.dumps(resultat,indent=2,default=int))
    print(json.dumps({k:v for k,v in resultat.items() if k not in ('adoption','predictions','buts')},default=int))


if __name__=='__main__':valider(Path(__file__).resolve().parent)
