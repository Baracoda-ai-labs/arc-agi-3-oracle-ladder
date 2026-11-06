import numpy as np
from chaine_coherente import Chaine
from chrysalide.arc3.moteur import MoteurFormel


def test_branches_comptees_independantes_apres_cache():
    image=np.zeros((64,64),dtype=int).tolist()
    p={'version':'0.2','etat':{'n':0},'regles':[{'nom':'compter', 'quand':True,
        'alors':[['poser','n',['+',['etat','n'],1]]]}]}
    c=Chaine(MoteurFormel(),p,[image,image],[{'actions':[{'action':'UP'}]}],[('UP',)])
    _, premier=c.rejouer();assert premier is not None
    pc1,s1=premier;assert pc1.etat['n']==1
    _,(pc2,s2)=c.rejouer()
    pc1.step(s1,('UP',));pc1.step(s1,('UP',))
    pc2.step(s2,('UP',))
    assert pc1.etat['n']==3 and pc2.etat['n']==2
    _,(pc3,s3)=c.rejouer();assert pc3.etat['n']==1
    pc3.step(s3,('UP',));assert pc3.etat['n']==2
