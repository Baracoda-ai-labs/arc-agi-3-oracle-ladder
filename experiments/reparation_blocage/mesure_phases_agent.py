"""Chronométrage inclusif observateur : ne somme pas les mesures internes recouvrantes."""
from contextvars import ContextVar
from functools import wraps
import resource
import time

PILE=ContextVar('mesures_phases_agent',default=())


def horloges():
    enfants=resource.getrusage(resource.RUSAGE_CHILDREN)
    return {'mur_s':time.monotonic(),'cpu_parent_s':time.process_time(),
            'cpu_enfants_recoltes_s':enfants.ru_utime+enfants.ru_stime}


def mesurer(phase):
    """Décorateur sans changement des arguments/résultat ; récursion explicitement imbriquée."""
    def decorer(fn):
        @wraps(fn)
        def mesurer_appel(self,*args,**kwargs):
            journal=getattr(self,'journal',None)
            if not isinstance(journal,list):return fn(self,*args,**kwargs)
            debut=horloges();index=len(journal);pile=PILE.get();enfants=[]
            contexte={'phase':phase,'enfants':enfants};token=PILE.set((*pile,contexte))
            observations={'reconstruction_demandee':bool(getattr(self,'reconstruction',False)),
                          'images':len(getattr(self,'images',())),
                          'actions':len(getattr(self,'actions',())),
                          'modeles_avant':len(getattr(self,'chaines',{})),
                          'dernier_evenement':journal[-1].get('type') if journal else None,
                          'raison_causale':'non_instrumentee_ne_pas_inferer_du_dernier_evenement'}
            resultat=None;erreur=None
            try:
                resultat=fn(self,*args,**kwargs);return resultat
            except BaseException as exc:
                erreur=type(exc).__name__;raise
            finally:
                fin=horloges();PILE.reset(token)
                durees={k:max(0.,fin[k]-debut[k]) for k in debut}
                # Seulement enfants directs : leurs durées incluent leurs propres descendants.
                directs={k:sum(c['durees_inclusives'][k] for c in enfants) for k in debut}
                propres={k:max(0.,durees[k]-directs[k]) for k in debut}
                nouveaux=journal[index:]
                ev={'type':'mesure_phase_agent','phase':phase,'parent_phase':pile[-1]['phase'] if pile else None,
                    'profondeur':len(pile),'index_journal_debut':index,'coup':len(getattr(self,'actions',()))+1,
                    'contexte_entree':observations,'durees_inclusives':durees,
                    'durees_hors_enfants_instrumentes':propres,
                    'enfants_directs':[{'phase':c['phase'],'durees_inclusives':c['durees_inclusives']} for c in enfants],
                    'evenements_admission':sum(e.get('type')=='admission' for e in nouveaux),
                    'evenements_admission_valides':sum(e.get('type')=='admission' and e.get('controle',{}).get('rejeu') is True for e in nouveaux),
                    'modeles_apres':len(getattr(self,'chaines',{})),
                    'sortie_statut':resultat.get('statut') if isinstance(resultat,dict) else None,
                    'exception':erreur,
                    'portee':'CPU processus + enfants termines recoltes ; pas temps CPU par thread ni enfants actifs',
                    'addition':'ne pas sommer phases inclusives imbriquees ni timings internes deja journalises'}
                journal.append(ev)
                if pile:pile[-1]['enfants'].append(ev)
        return mesurer_appel
    return decorer
