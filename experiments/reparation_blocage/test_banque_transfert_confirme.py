"""Branche confirmée réelle, archive immuable ; aucune recherche ni SDK."""
import copy,hashlib
from pathlib import Path
import cloudpickle
import numpy as np
from campagne_moteur_commun import commande,valider
from test_campagne_moteur_commun import manifeste
from session_chaine_generique import arguments_session,agent_transfere,configurer_recherche,configurer_composition
from memoire_observations import episode_observe


def test_banque_frontieres_et_options_conservees_sur_transfert_confirme(tmp_path):
    source=Path(__file__).parent/'runs/ka59_controleur_corrige72_1/agent.pkl'
    blob=source.read_bytes();a=cloudpickle.loads(blob)
    g=np.zeros((2,2),dtype=int)
    ep=episode_observe([g,g+1],[1],['niveau'],[[g,g+1]])
    ep['provenance']['fixture']='episode anterieur synthetique sans lien avec jeu'
    a.observations_episodes=[ep]
    m=manifeste();m.update(recherche_prolongee=True,recherche_workers=1)
    argv=commande('ka59',1,tmp_path,valider(m));args=arguments_session().parse_args(argv[3:])
    configurer_recherche(a,args.recherche_prolongee,workers=args.recherche_workers)
    configurer_composition(a,args.composition_contextuelle_auto)
    avant=copy.deepcopy(a.modele_gagnant.programme)
    courant=episode_observe(a.images,a.actions,a.issues,a.films)
    n=agent_transfere(a,a.images[-1],[1,2,3,4,6])
    assert n.chaines and not n.reconstruction
    assert n.recherche_prolongee and n.recherche_prolongee_workers==1 and n.composition_contextuelle_auto
    assert len(n.observations_episodes)==2
    ancien,nouveau=n.observations_episodes
    assert ancien['provenance']['sha256_contenu']==ep['provenance']['sha256_contenu']
    assert nouveau['provenance']['sha256_contenu']==courant['provenance']['sha256_contenu']
    assert ancien['provenance']['fixture']==ep['provenance']['fixture']
    assert nouveau['provenance']['transition_victorieuse']==len(a.actions)
    assert nouveau['provenance']['image_post_transition_utilisable_comme_but'] is False
    assert np.array_equal(nouveau['films'][-1],a.films[-1])
    assert n.actions==[] and len(n.images)==1
    assert a.modele_gagnant.programme==avant and len(a.observations_episodes)==1
    nouveau['grilles'][0][0][0]=99
    ancien['grilles'][0][0,0]=99
    assert np.asarray(a.images[0])[0,0]!=99 and ep['grilles'][0][0,0]==0
    assert hashlib.sha256(source.read_bytes()).digest()==hashlib.sha256(blob).digest()
