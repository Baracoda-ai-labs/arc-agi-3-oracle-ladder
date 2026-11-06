"""Fonctions assemblables. Contrats = préconditions, effets et portée logique."""
CONTRATS={
 'ajouter_memoire':dict(inputs=['routes','route','capacity>=1','policy clear|fifo'],outputs=['routes'],logical='ASP borné pour la sélection des indices; chemins Python'),
 'porte':dict(inputs=['kind held|inverse|toggle','occupied','bit'],outputs=['open'],logical='ASP table booléenne'),
 'collision':dict(inputs=['empreintes','poses'],outputs=['overlap'],logical='hors logique, calcul géométrique Python'),
 'perception':dict(inputs=['images exactes'],outputs=['objets candidats'],logical='hors logique, hypothèses révisables')}
def ajouter_memoire(routes,route,capacity,policy):
 if capacity<1 or policy not in ('clear','fifo'):raise ValueError('contrat mémoire')
 if len(routes)>=capacity:return () if policy=='clear' else (routes+(route,))[-capacity:]
 return routes+(route,)
def porte(kind,occupied,bit=False):
 if kind=='held':return bool(occupied)
 if kind=='inverse':return not occupied
 if kind=='toggle':return bool(bit)
 raise ValueError('contrat porte')
def compiler_portes():
 return '\n'.join(f'ouvert({k},{o},{b}).' for k in ('held','inverse','toggle') for o in (0,1) for b in (0,1) if porte(k,o,b))+'\n#show ouvert/3.\n'

CONTRATS['economie']=dict(inputs=['jauge dessinée','action','état terminal public'],outputs=['intervalle énergie','coûts compatibles','recharges observées','autorisation séquence'],logical='versions numériques Python; compilation ASP de borne sûre')
CONTRATS['portail']=dict(inputs=['position','liaison visuelle','occupation déclencheur'],outputs=['position transformée'],logical='hors logique, géométrie Python')
def compiler_budget(energy_lower,action_costs):
 # Conversion conservatrice: énergie arrondie en dessous, coûts au dessus.
 import math
 lines=[f'energie({math.floor(energy_lower)}).']
 for i,c in enumerate(action_costs):lines.append(f'cout({i},{math.ceil(c)}).')
 return '\n'.join(lines)+'\nautorise(A) :- cout(A,C), energie(E), E>C.\n#show autorise/1.\n'
def compiler_memoire(n,capacity,policy):
 if n<0 or capacity<1 or policy not in ('clear','fifo'):raise ValueError('contrat mémoire ASP')
 return f'''n({n}). capacite({capacity}). politique({policy}).
ancien(0..{n-1}).
garde(I) :- ancien(I), n(N), capacite(C), N<C.
garde(N) :- n(N), capacite(C), N<C.
garde(I) :- ancien(I), n(N), capacite(C), N>=C, politique(fifo), I>N-C.
garde(N) :- n(N), capacite(C), N>=C, politique(fifo).
#show garde/1.
'''
