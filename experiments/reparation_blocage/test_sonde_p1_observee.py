import json
from pathlib import Path
import numpy as np
from chaine_agent_integree import AgentIntegre

def test_sonde_reelle_reutilisee_confronte_les_modeles():
    p=Path(__file__).parent/'runs/re86_ancre_reel_1/N1/partie'
    z=np.load(p.with_suffix('.npz'));rows=json.loads(p.with_suffix('.json').read_text())['rows']
    a=AgentIntegre(list(z['images'][:9]),[r['action'] for r in rows[:8]],
        [z[f'film_{i+1}'] for i in range(8)],['continue']*8,
        legacy_sans_but=True,utilite_sondes=True,exploration_p1=True,routage_classes=True)
    a.reconstruire()
    # Action9 déjà jouée : pas de nouveau SDK, choix d'action laissé au proposeur.
    d={'statut':'experience_conditionnelle','actions':[rows[8]['action']]}
    a._suivre_experience(d)
    assert d['modeles'] and d['predictions']
    a.attente=d
    result=a.observer(rows[8]['action'],z['images'][9],z['film_9'],'continue')
    assert result['resultats']
    assert a.attente is None
