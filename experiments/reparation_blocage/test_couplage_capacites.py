from pathlib import Path
from avancer_agent_relais import charger_agent
from relation_clic_observee import proposer_agent


def source():
 return charger_agent(Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n2_couplage60/agent.pkl')


def test_baseline_puis_intervention_sur_support_sans_but():
 a=source();d=proposer_agent(a,[1,2,3,4,6,7])
 assert d['origine']=='baseline_couplage_navigation' and d['actions']==[3]
 assert len(d['objectif_experience']['route_hypothetique'])==3
 a.actions.append(3);a.images.append(a.images[-1].copy());a.films.append([a.images[-1]]);a.issues.append('continue')
 d=proposer_agent(a,[1,2,3,4,6,7])
 assert d['origine']=='intervention_relation_pour_couplage' and d['actions']==[['clic',14,17]]
 assert d['but']=='inconnu'


def test_aucune_action_hors_offre():
 from couplage_capacites import proposer
 a=source();assert proposer(a,[6],a.memoire_relation_clic) is None


def test_comparaison_finale_respecte_offre():
 from couplage_capacites import proposer
 a=source();a.experience_couplage={'commande':3,'forme_cible':[1,1],'position_mobile':[48,14]}
 assert proposer(a,[6],a.memoire_relation_clic) is None


def test_route_reutilise_refus_de_selection_dans_experience():
 from couplage_capacites import route_relation
 a=source();regle=a.memoire_relation_clic['regle'];ps={(37,15),(43,15),(43,51)}
 refus={'positions':sorted(map(list,ps)),'sources':[[37,15],[43,15]],'destination':[49,15]}
 assert route_relation(ps,regle,(43,15),[refus])==[((43,15),(37,15),(31,15))]
 # Le refus n'est pas importé d'office dans une autre expérience.
 assert route_relation(ps,regle,(43,15))[0][2]==(49,15)


def test_marqueur_superpose_sur_mobile_reste_detecte():
 a=charger_agent(Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n2_chaine_couplage61/agent.pkl')
 d=proposer_agent(a,[1,2,3,4,6,7])
 assert d['origine']=='relation_clic_marqueur_confirme'
 assert d['marqueurs_observes'][0]['preuve']=='difference_locale_sur_destination_apres_selection'
 assert d['marqueurs_observes'][0]['n']==8
 assert d['prediction_partielle']['destination']==(49,15)
 assert a.experience_couplage['position_mobile']==[48,14]


def test_changement_hors_destination_ne_confirme_pas_marqueur():
 import numpy as np
 from marqueur_superpose import candidat
 a=np.zeros((8,8),dtype=int);b=a.copy();b[0,:]=2
 assert candidat(a,b,(3,3),[(0,0),(1,0),(0,1)]) is None
 b[3,3]=2
 assert candidat(a,b,(3,3),[(0,0),(1,0),(0,1)]) is None


def test_apres_superposition_comparaison_retrouve_ancre_hors_attribut():
 a=charger_agent(Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n2_marqueur_superpose67/agent.pkl')
 d=proposer_agent(a,[1,2,3,4,6,7])
 assert d['origine']=='comparaison_navigation_apres_relation' and d['actions']==[3]
 p=d['objectif_experience']['ancre_partielle']
 assert p['position']==[48,14] and p['identite']=='provisoire'
 assert a.diagnostic_prediction_partielle['exact'] is True


def test_attribut_ne_masque_pas_changement_hors_destination():
 import numpy as np
 from ancre_sous_attribut import retrouver
 a=charger_agent(Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n2_marqueur_superpose67/agent.pkl')
 d=proposer_agent(a,[1,2,3,4,6,7]);o=d['objectif_experience'];image=np.array(a.images[-1]).copy();image[14,48]=0
 assert retrouver(image,o['motif_mobile'],o['position_mobile'],a.dernier_contrat_relation) is None


def test_deplacement_sur_support_departage_objet_superpose():
 a=charger_agent(Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n2_comparaison68/agent.pkl')
 d=proposer_agent(a,[1,2,3,4,6,7])
 assert d['origine']=='experience_mouvement_conjoint' and d['actions']==[4]
 assert d['hypotheses']=={'independante':[49,15],'conjointe':[55,15]}
 assert d['but']=='inconnu'


def test_memoire_conjointe_reste_provisoire_et_sans_but():
 from sonde_mouvement_conjoint import memoriser
 a=charger_agent(Path(__file__).parent/'runs/stream_multijeux_26_10/lf52_n2_conjoint69/agent.pkl')
 r=memoriser(a,a.experience_couplage,a.memoire_relation_clic)
 assert r['coup_preuve']==69 and r['decalage']==[1,1] and r['vecteur_observe']==[6,0]
 assert not r['but_certifie'] and not r['contenance_certifiee'] and not r['transfert_valide']
