import copy,json,re
from pathlib import Path
import numpy as np
from chaine_agent_integree import AgentIntegre,canon,lots
from chaine_coherente import Chaine
from perception_routee import completion_causale
from representation_legacy_sans_but import construire
from chrysalide.arc3.logique.export_langage import exporter
from revision_solidite import proposer
R=Path(__file__).parent

def test_projection_repare_53_conserve_prefixe_et_predit_suite():
    p=R/'runs/re86_revision_solidite_reel_1'
    z=np.load(p/'N1/partie.npz')
    rows=json.loads((p/'N1/partie.json').read_text())['rows']
    actions=[r['action'] for r in rows]
    lecon=next(l for l in json.loads((p/'lecons_revision.json').read_text())
               if l['entree']['coup_disponible']==18)
    with completion_causale():
        initial,_=construire({'grilles':z['images'][:9],'lots':lots(actions[:8])},echelle=(1,0,0))
    m=initial.perception
    m.th_releve.solides-=frozenset(map(int,re.findall(r'non_solide_(\d+)',lecon['modele_apres'])))
    programme,_=exporter(m.th_releve,m.tr.taille)
    assert programme==lecon['cible']['programme_apres']
    c=Chaine(m,programme,z['images'][:54].tolist(),lots(actions[:53]),[],
             coups_deja_joues=53,films=[z[f'film_{i+1}'] for i in range(53)])
    assert c.rejouer()[0]['premiere_divergence']==53
    candidates,diag=proposer(c,projection=True)
    assert len(candidates)==1
    nom,new=candidates[0]
    assert new.revision_locale['operateur']=='debord_visible'
    assert new.perception.th_releve.moves==m.th_releve.moves
    assert new.perception.tr.exclues==m.tr.exclues
    assert new.rejouer()[0]['transitions']==53
    agent=AgentIntegre([],[],[],[])
    for i in [53,54]:
        pred=agent._predire(new,canon(actions[i]))
        assert np.array_equal(pred['image'],new.perception.vue(z['images'][i+1]))
        # Étendre uniquement après avoir confronté la prédiction à l'observation.
        new=Chaine(new.perception,new.programme,z['images'][:i+2].tolist(),lots(actions[:i+1]),[],
                   coups_deja_joues=i+1,films=[z[f'film_{k+1}'] for k in range(i+1)])
        assert new.rejouer()[1] is not None
