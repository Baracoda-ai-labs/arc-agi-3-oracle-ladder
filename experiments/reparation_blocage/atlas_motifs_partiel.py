"""Mémoire locale de transitions de motifs, pas induction d'une loi géométrique."""
import copy
from collections import defaultdict
import numpy as np
from classification_prefixe import _objets
from chrysalide.arc3.objets_temps import Pisteur


class AtlasMotifsPartiel:
    def __init__(self, images, actions, films, masque=(), preuve_masque=None):
        if len(images)!=len(actions)+1 or len(films)!=len(actions): raise ValueError('Prefixe incomplet')
        if masque and not preuve_masque: raise ValueError('Masque sans preuve')
        self.masque=tuple(masque);self.fond=int(np.unique(images[0],return_counts=True)[0][np.argmax(np.unique(images[0],return_counts=True)[1])])
        self.pisteur=Pisteur(revisable=True,chevauche=True);self.tables=defaultdict(set);self.supports=defaultdict(list)
        before=self._voir(images[0])
        for i,(a,f,im) in enumerate(zip(actions,films,images[1:])):
            if not len(f) or not np.array_equal(f[-1],im):raise ValueError('Film non aligne')
            after=None
            for frame in f:after=self._voir(frame)
            for ident in before.keys() & after.keys():
                b,c=before[ident],after[ident]
                if b['bord'] or c['bord'] or b['dessin']==c['dessin']:continue
                key=(b['dessin'],repr(a));value=(c['dessin'],tuple(v-u for u,v in zip(b['origine'],c['origine'])))
                self.tables[key].add(value);self.supports[key].append(i+1)
            before=after
        self.actuel=before;self.rang=len(actions);self.attente=None

    def _voir(self,image):
        im=np.asarray(image).copy()
        for y,x in self.masque:im[y,x]=self.fond
        return _objets(self.pisteur.observer(im),im)

    def predire(self,action):
        if self.attente is not None:raise ValueError('Observation attendue')
        predictions=[]
        for ident,b in self.actuel.items():
            values=self.tables.get((b['dessin'],repr(action)),set())
            if len(values)!=1:continue
            dessin,delta=next(iter(values))
            predictions.append({'piste':ident,'dessin':dessin,'origine':tuple(x+d for x,d in zip(b['origine'],delta)),'supports':self.supports[(b['dessin'],repr(action))]})
        self.attente=(copy.deepcopy(action),copy.deepcopy(predictions))
        return {'predictions':copy.deepcopy(predictions),'couverts':['motif_et_origine_de_pistes_memorisees'],'inconnus':['identite_causale','reste_image','issue','contact','mecanisme'],'portee':'table motif/action observee; identite par chevauchement hypothetique','droit_action':False,'rang':self.rang}

    def observer(self,action,image,film):
        if self.attente is None or self.attente[0]!=action:raise ValueError('Sans prediction prospective')
        if not len(film) or not np.array_equal(film[-1],image):raise ValueError('Film non aligne')
        for frame in film:self.actuel=self._voir(frame)
        result=[]
        for p in self.attente[1]:
            a=self.actuel.get(p['piste'])
            result.append({'piste':p['piste'],'verdict':'identite_non_retrouvee' if a is None else 'compatible' if a['dessin']==p['dessin'] and a['origine']==p['origine'] else 'refute','supports':p['supports']})
        self.attente=None;self.rang+=1
        return result
