"""Quatre hypothèses perceptives/interactives, fonctions adaptées en mémoire seulement."""
import inspect
import json
import os
import textwrap
from pathlib import Path
import numpy as np
from chaine_agent_integree import lots
from chaine_coherente import Chaine
from chrysalide.arc3.moteur import MoteurC,_codes_c
from chrysalide.arc3.logique import faits,induction,theorie,export_langage


def variante(fn,ancien,neuf,globales):
    texte=textwrap.dedent(inspect.getsource(fn))
    assert ancien in texte
    espace=dict(fn.__globals__);espace.update(globales)
    exec(compile(texte.replace(ancien,neuf),'<audit_hitbox>','exec'),espace)
    return espace[fn.__name__]


def main():
    base=Path(__file__).parent;source=base/'runs/session_ft09_cycle3_1/N5'
    archive=json.loads((source/'partie.json').read_text())
    images=np.load(source/'partie.npz')['images'][:101].copy();ls=lots(archive['actions'][:100])
    assert len(ls)==100
    os.environ['CHRYS_DIAGONALES']='0'
    tr0=faits.Trajectoire(images[:9].tolist(),_codes_c(ls[:8]))
    diagonales=frozenset().union(*(faits.couleurs_diagonales(c,tr0.fond,tr0.exclues) for c in tr0.cases))
    originals=(faits.couleurs_diagonales,induction.faits_clic,induction.trouver_motif_formes,theorie.Theorie.clic,export_langage._clics)
    resultat={'source':str(source.resolve()),'prefixe':8,'suffixe':92,'sdk':0,'buts_non_induits_sur_suffixe':True,'candidats':[]}
    resultat['actions_suffixe_inedites']=sorted(set(map(tuple,archive['actions'][8:100]))-set(map(tuple,archive['actions'][:8])))
    for connexite in (4,8):
      for hitbox in ('pixels','boite'):
        faits.couleurs_diagonales=lambda *a:diagonales
        os.environ['CHRYS_DIAGONALES']='1' if connexite==8 else '0'
        tr=faits.Trajectoire(images[:9].tolist(),_codes_c(ls[:8]))
        actives=set()
        for avant,apres in zip(tr.etats,tr.etats[1:]):
            suivant={(o[1],o[2],o[3]):o[0] for o in apres}
            actives.update(o[1] for o in avant if suivant.get((o[1],o[2],o[3]),o[0])!=o[0])
        def hit(o,x,y):
            return o[1] in actives and min(a for a,b in o[1])+o[2]<=x<=max(a for a,b in o[1])+o[2] and min(b for a,b in o[1])+o[3]<=y<=max(b for a,b in o[1])+o[3]
        try:
            if hitbox=='boite':
                induction.faits_clic=variante(originals[1],'(a[1], a[2]) in cells(o)','_audit_hit(o,a[1],a[2])',{'_audit_hit':hit})
                induction.trouver_motif_formes=variante(originals[2],'(x, y) in cells(o)','_audit_hit(o,x,y)',{'_audit_hit':hit})
                theorie.Theorie.clic=variante(originals[3],'(x, y) in cells(o)','_audit_hit(o,x,y)',{'_audit_hit':hit})
                sous=['filtrer','$s',['objets',{}],['et',['<=',['x','$s'],['elem',['case_clic'],0]],['<',['elem',['case_clic'],0],['+',['x','$s'],['largeur','$s']]],['<=',['y','$s'],['elem',['case_clic'],1]],['<',['elem',['case_clic'],1],['+',['y','$s'],['hauteur','$s']]]]]
                def forme_exacte(v,th):
                    return [['ou',False,*[export_langage._forme_egale(v,f) for f in th.formes_bascule]]] if th.formes_bascule else []
                export_langage._clics=variante(originals[4],'["a", ["elem", ["case_clic"], 0], ["elem", ["case_clic"], 1]]',repr(sous),{'_forme_bascule':forme_exacte})
            th,infos=induction.induire([(tr,None,None)],limite_s=2)
            prog,non=export_langage.exporter(th,tr.taille)
            m=MoteurC();m.tr=tr;m.th_releve=th;m._couches=th.couches()
            c=Chaine(m,prog,images[:9].tolist(),ls[:8],[],reserve=1000)
            controle,etat=c.rejouer()
            d=dict(connexite=connexite,hitbox=hitbox,diagonales=sorted(tr.diagonales),formes_actives=sorted(map(len,actives)),
                bascule=th.bascule,motif=sorted(th.motif),motifs_par_forme=[(len(f),len(v)) for f,v in th.motif_formes],
                induction=infos,non_exporte=non,controle_prefixe=controle,admis=etat is not None)
            d.update(rejeu_theorie=theorie.rejeu(th,tr),configurations_locales=len(th.clic_configs),
                     formes_bascule=sorted(map(len,th.formes_bascule)),forme_export_exacte=hitbox=='boite')
            if etat is not None:
                complet=Chaine(m,prog,images.tolist(),ls,[],reserve=1000)
                d['controle_suffixe_gele']=complet.rejouer()[0]
            resultat['candidats'].append(d)
            print(json.dumps(d,ensure_ascii=False,default=str),flush=True)
        finally:
            faits.couleurs_diagonales,induction.faits_clic,induction.trouver_motif_formes,theorie.Theorie.clic,export_langage._clics=originals
    (base/'AUDIT_HITBOX_MOTIF_FT09_N5.json').write_text(json.dumps(resultat,ensure_ascii=False,indent=2,default=str)+'\n')

if __name__=='__main__':main()
