"""Classification → représentations existantes → admission ou diagnostic, jamais oracle."""
import os,copy
from contextlib import contextmanager
from representation_legacy_sans_but import construire
from ontologie_extensible import FicheRevision
from chrysalide.arc3.logique.diagnostic import diagnostiquer,contradictions,appliquer
from chrysalide.arc3.logique.theorie import rejeu
from chrysalide.langue.ontologie_formelle import PROJECTION

@contextmanager
def completion_causale():
    # Le moteur hérité expose ce profil par environnement. Portée synchrone et restaurée.
    old=os.environ.get('CHRYS_AMODAL')
    os.environ['CHRYS_AMODAL']='1'
    try:yield
    finally:
        if old is None:os.environ.pop('CHRYS_AMODAL',None)
        else:os.environ['CHRYS_AMODAL']=old

def proposer(description,historique,toutes=False):
    preuves=[x for x in description['transformation_motif']['preuves'] if not x['region_bord']]
    if not preuves:return [],{'statut':'non_requis','candidats':[]}
    report={'statut':'representations_evaluees','declencheur':'transformation_motif_hors_interface','preuves':preuves,'contrat_projection':copy.deepcopy(PROJECTION['completion_scene']),'candidats':[]}
    admitted=[]
    for name,scale in [('completion_causale',None),('completion_causale_pixels',(1,0,0))]:
        with completion_causale():
            c,r=construire(historique,limite_s=2,echelle=scale)
            th,tr=c.perception.th_releve,c.perception.tr
            diag=diagnostiquer(th,tr)
            essais=[]
            if diag is not None:
                score0=rejeu(th,tr)[0]
                for correction in diag['corrections']:
                    if correction[0]=='masquer':continue
                    candidate=appliquer(th,correction);score=rejeu(candidate,tr)[0]
                    essais.append({'correction':correction,'transitions_conformes_avant':score0,'transitions_conformes_apres':score,'amelioration_stricte':score>score0,'adoptee':False})
            fiche=FicheRevision(th,[],{'representation':name,'prefixe':len(tr.actions)}).rapport()
            entry={'nom':name,'echelle':tr.s,'controle':r,'diagnostic':diag,'corrections_evaluees':essais,'contradictions_perceptives':contradictions(tr),'metamodele':fiche,'droit_planifier':r['admis'],'aucune_extension_masque':True}
        report['candidats'].append(entry)
        if r['admis']:admitted.append((name,c))
    if toutes or not admitted:
        from perception_ancre_complete import TrajectoireAncreComplete
        try:
            c,r=construire(historique,limite_s=2,trajectoire_factory=TrajectoireAncreComplete,
                          presence_prudente=True,dedoublonne_poussee=True,ancre_complete=True)
            entry={'nom':'ancre_forme_projection','controle':r,'diagnostic':None,
                   'droit_planifier':r['admis'],'aucune_extension_masque':True,
                   'portee':'ancre bornee candidate ; completion seulement si projection unique'}
            report['candidats'].append(entry)
            if r['admis']:admitted.append(('ancre_forme_projection',c))
        except ValueError as exc:
            report['candidats'].append({'nom':'ancre_forme_projection','diagnostic':None,
                'droit_planifier':False,'refus':str(exc)})
    report['diagnostics_accessibles']=sum(x['diagnostic'] is not None for x in report['candidats'])
    report['admis']=len(admitted)
    return admitted,report
