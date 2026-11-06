from pathlib import Path
import copy,cloudpickle
from chaine_coherente import Chaine
R=Path(__file__).parent/'runs/ka59_n4_contact_classe5_auto1'

def test_contact_classe_et_deux_niveaux():
    a=cloudpickle.loads((R/'fixture_agent5.pkl').read_bytes());c=next(iter(a.chaines.values()))
    assert c.rejouer()[0]['transitions']==5
    nouveau=c.programme['regles'][-1]
    assert nouveau['alors'][0][3][0][1][2][2][1]=={'tag':'bloqueur','couleur':15}
    source=c.modele_source_transfert;p=copy.deepcopy(source.programme);p['regles'].append(copy.deepcopy(nouveau))
    v=copy.deepcopy(source.perception);v.programme_transfere=p
    test=Chaine(v,p,source.grilles,source.lots,source.actions,films=[e['images'] if e else None for e in source.films.entrees])
    controle,etat=test.rejouer()
    assert etat and controle['transitions']==62 and controle['compilation_fidele']
    assert c.preuve_transfert_roles['but_source_confirme_par_victoire']
    assert c.but_hypothese_non_confirmee and c.preuve_but_elargi

def test_blanc_universel_contredit_source():
    a=cloudpickle.loads((R/'fixture_agent5.pkl').read_bytes());c=next(iter(a.chaines.values()))
    source=c.modele_source_transfert;r=copy.deepcopy(c.programme['regles'][-1]);del r['alors'][0][3][0][1][2][2][1]['couleur']
    p=copy.deepcopy(source.programme);p['regles'].append(r);v=copy.deepcopy(source.perception);v.programme_transfere=p
    test=Chaine(v,p,source.grilles,source.lots,source.actions,films=[e['images'] if e else None for e in source.films.entrees])
    assert test.rejouer()[1] is None
