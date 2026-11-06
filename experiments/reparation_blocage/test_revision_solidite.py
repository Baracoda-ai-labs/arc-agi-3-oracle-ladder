import json
from pathlib import Path
import numpy as np
from chaine_agent_integree import AgentIntegre,canon
R=Path(__file__).parent

def cas():
    p=R/'runs/re86_aiguillage_reel_2/N1/partie'
    z=np.load(p.with_suffix('.npz'))
    rows=json.loads(p.with_suffix('.json').read_text())['rows']
    a=AgentIntegre(z['images'][:9],[r['action'] for r in rows[:8]],
        [z[f'film_{i+1}'] for i in range(8)],['continue']*8,legacy_sans_but=True,
        exploration_p1=True,utilite_sondes=True,aiguillage_provisoire=True,revision_solidite=True)
    a.reconstruire()
    for i in range(8,11):
        d={'actions':[rows[i]['action']],'predictions':[[]]}
        a._suivre_experience(d);a.attente=d
        a.observer(rows[i]['action'],z['images'][i+1],z[f'film_{i+1}'],'continue')
    return a,z,rows

def test_correction_prefixe_et_prediction_suivante_sans_reapprentissage():
    a,z,rows=cas()
    repaired=[c for c in a.chaines.values() if hasattr(c,'revision_locale')]
    assert repaired
    for c in repaired:
        check,state=c.rejouer()
        assert state is not None and check['compilation_fidele']
        assert c.revision_locale['generalisation'] is False
    pixel=next(c for c in repaired if c.perception.tr.s==1)
    pred=a._predire(pixel,canon(rows[11]['action']))
    assert np.array_equal(pred['image'],pixel.perception.vue(z['images'][12]))
    result=a.decider([1,2,3,4],secondes=30)
    assert result['origine']=='consequence_revision'
    assert result['actions']!=[rows[11]['action']]
    assert result['modeles'] and result['diagnostic']['choix']
    (R/'runs/diagnostic_refutation_re86_1/controle_correction.json').write_text(json.dumps({
        'revisions':len(repaired),'prefixe_rejoue':11,'prediction_coup12_exacte':True,
        'ancienne_action12':rows[11]['action'],'nouvelle_sonde':result['actions'],
        'statut':'verification_sur_traces_deja_consultees','nouveaux_coups':0},indent=2))

def test_reparateur_ne_fabrique_pas_un_contrat():
    from revision_solidite import proposer
    from types import SimpleNamespace
    assert proposer(SimpleNamespace(perception=object()))[0]==[]
