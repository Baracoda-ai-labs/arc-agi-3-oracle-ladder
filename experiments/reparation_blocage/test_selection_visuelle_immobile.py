from pathlib import Path
import json
import numpy as np
import pytest
from selection_visuelle_immobile import analyser,proposer
from issues_observees import issue_sdk


def traces(n=19):
    p=Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_trace19/partie'
    rows=json.loads(p.with_suffix('.json').read_text())['rows'][:n]
    with np.load(p.with_suffix('.npz')) as z:
        images=z['images'][:n+1].copy();films=[z[f'film_{i+1}'].copy() for i in range(n)]
    return images,[r['action'] for r in rows],films,[issue_sdk(r['state'],r['levels_completed'],0) for r in rows]


def test_activation_sans_mouvement_ne_prouve_pas_controle():
    h=analyser(*traces(18))[-1]
    assert h['coup_activation']==18 and h['pixels_attribut']==28
    assert not h['mouvement_observe'] and not h['controle_valide'] and not h['but_valide']
    assert h['retours_observes']==[]
    assert proposer(*traces(18),[6]) is None


def test_retour19_prepare_experience_nouvelle_pas_sequence_aveugle():
    d=proposer(*traces(),[1,2,3,4,6,7])
    assert d['hypothese_selection']['retours_observes']==[19]
    assert d['actions']==[['clic',25,19]]
    assert d['cible_experience_nouvelle']!=d['actions'][0]
    assert d['predictions']==[[]] and d['but']=='inconnu'
    assert d['cle_integrale_conservee'] and d['projection_pas_preuve_equivalence']


def test_permutation_couleurs_pas_regle_jeu():
    im,ac,fl,iss=traces();palette=np.arange(16)[::-1]
    a=proposer(im,ac,fl,iss,[6]);b=proposer(palette[im],ac,[palette[f] for f in fl],iss,[6])
    assert b['actions']==a['actions']
    assert b['cible_experience_nouvelle']==a['cible_experience_nouvelle']


def test_nouveau_contexte_observe_avant_sonde_et_pas_boucle():
    im,ac,fl,iss=traces();actif=im[18].copy()
    d=proposer(np.concatenate([im,[actif]]),ac+[ac[17]],fl+[np.array([actif])],iss+['continue'],[6])
    assert d['raison']=='sonder_marqueur_contextuel'
    assert d['actions']==[d['cible_experience_nouvelle']]


def test_pas_clic_sans_offre():
    assert proposer(*traces(),[1,2]) is None


def test_historique_incomplet_refuse():
    im,ac,fl,iss=traces()
    with pytest.raises(ValueError):analyser(im[:-1],ac,fl,iss)


def test_raccord_decider_et_ablation_meme_prefixe(monkeypatch):
    from chaine_agent_integree import AgentIntegre
    import selection_visuelle_immobile as module
    def agent():
        a=AgentIntegre(*traces(),limite=1000,exploration_p1=True)
        a.reconstruction=False # isole le repli, après refus des modèles
        return a
    actif=agent().decider([1,2,3,4,6,7],secondes=0)
    monkeypatch.setattr(module,'proposer',lambda *args:None)
    temoin=agent().decider([1,2,3,4,6,7],secondes=0)
    assert actif['origine']=='selection_visuelle_immobile'
    assert temoin['origine']=='p1_graphe_observe'
    assert actif['actions']!=temoin['actions']
