from pathlib import Path
import copy,cloudpickle
from memoire_observations import episode_observe
from segments_contextuels_observes import proposer_segments

R=Path(__file__).parent

def donnees():
    a=cloudpickle.loads((R/'runs/ar25_memoire_episodes52_1/agent.pkl').read_bytes())
    p=next(iter(a.modeles_contextes_suspendus.values()))['chaine']
    e=a.observations_episodes[0]
    # Coup22 est la frontière d'accès. 23 et suivants ne sont pas fournis au sélecteur.
    prefixe=episode_observe(e['grilles'][:23],e['actions'][:22],e['issues'][:22],e['films'][:22])
    return p,e,prefixe


def test_segment_trouve_sans_indices_fournis_ni_suffixe():
    p,e,prefixe=donnees();avant=cloudpickle.dumps(p)
    cs,d=proposer_segments(p,[prefixe])
    assert len(cs)==1,d
    c=cs[0];assert c.preuve_segment_contextuel['transitions_induction']==[18,22]
    assert c.preuve_segment_contextuel['transitions_masque']==[1,17]
    assert c.rejouer()[0]['transitions']==5 and c.rejouer()[0]['compilation_fidele']
    assert len(c.films.entrees)==5 and c.preuve_segment_contextuel['episode_sha256']==prefixe['provenance']['sha256_contenu']
    assert cloudpickle.dumps(p)==avant
    assert not any('niveau_suivant' in str(r) for r in c.programme['regles'])


def test_episodes_non_fusionnes_et_empreinte_fausse_refusee():
    p,e,prefixe=donnees()
    # Même segment sans passé antérieur : aucun masque acquis, pas de récupération implicite.
    local=episode_observe(e['grilles'][17:23],e['actions'][17:22],e['issues'][17:22],e['films'][17:22])
    assert not proposer_segments(p,[local])[0]
    faux=copy.deepcopy(prefixe);faux['actions'][0]=1
    assert not proposer_segments(p,[faux])[0]
    assert not proposer_segments(p,[])[0]
