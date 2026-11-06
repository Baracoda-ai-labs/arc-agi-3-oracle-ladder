"""Audit hors SDK : préfixe d'apprentissage séparé du suffixe archivé."""
import json
import copy
import os
import time
from pathlib import Path
import numpy as np
from chaine_agent_integree import lots
from chaine_coherente import Chaine
from chrysalide.arc3.moteur import MoteurC
from chrysalide.arc3.logique.export_langage import exporter
from chrysalide.arc3.logique import transfert


def main(conserver=False, prefixe=3, contre_exemple=False, flag=1, coherence=1):
    racine = Path(__file__).parent
    source = racine / 'runs/session_ft09_transfert_memoire1'
    def lire(n):
        p = source / f'N{n}' / 'partie'
        j = json.loads(p.with_suffix('.json').read_text())
        return np.load(p.with_suffix('.npz'))['images'].tolist(), lots(j['actions']), j
    precedents = []
    for n in (1, 2):
        gs, ls, j = lire(n)
        assert j['rows'][-1]['levels_completed'] >= n
        precedents.append(dict(grilles=gs[:-1], lots=ls[:-1], finale=ls[-1]))
    gs, ls, _ = lire(3)
    h = dict(grilles=gs[:prefixe+1], lots=ls[:prefixe], precedents=precedents)
    os.environ.update(CHRYS_TRANSFERT=str(flag), CHRYS_BUT_SUPPOSE='1', CHRYS_CHAINE_COHERENTE=str(coherence), CHRYS_REPARATION_BLOCAGE='0')
    d = dict(source=str(source.resolve()), prefixe=prefixe, suffixe_separe=len(ls)-prefixe, nouveaux_coups_sdk=0, budget=10)
    d['CHRYS_TRANSFERT'] = flag
    d['CHRYS_CHAINE_COHERENTE'] = coherence
    original = transfert.transferer
    def observe(th, tr, rej):
        t, mapping, ok = original(th, tr, rej)
        d['renommage'] = dict(mapping=mapping, exactes=ok, total=len(tr.actions), but_source=repr(th.but), but_renomme=repr(t.but))
        return t, mapping, ok
    transfert.transferer = observe
    prior = None
    if conserver:
        ng, nl, _ = lire(2)
        n2 = MoteurC(budget=10, limite_plan=100000)
        r2 = n2.proposer(dict(grilles=ng[:2], lots=nl[:1], precedents=precedents[:1]))
        if r2 is None:
            raise AssertionError(('reconstruction N2 sans plan', n2.infos))
        prior = copy.deepcopy(n2.th_plan)
        avant_victoire = Chaine(n2, r2[1], ng[:-1], nl[:-1], [], coups_deja_joues=len(nl)-1)
        check, etat = avant_victoire.rejouer()
        finale = nl[-1]['actions'][0]
        gagnant, preuve = avant_victoire.verifier_plan([('MOUSE', finale['row'], finale['col'])])
        assert etat is not None and gagnant, (check, preuve)
        d['memoire_N2'] = dict(but=repr(prior.but), bascule=prior.bascule, controle=check,
                               finale_verifiee=gagnant, preuve_finale=preuve,
                               plan_reconstruit=r2[0], victoire_reelle=True)
    prior_avant = copy.deepcopy(prior)
    from chrysalide.arc3.logique import induction
    from chrysalide.arc3.logique.theorie import rejeu
    induction_originale = induction.induire
    def affiner(sources, **kwargs):
        th, info = induction_originale(sources, **kwargs)
        tr = sources[0][0]
        ok, n, premier = rejeu(th, tr)
        if premier is not None:
            autre, details = induction_originale([(tr, [premier], None)], limite_s=2)
            fusion = transfert.fusionner(th, autre)
            couverture = rejeu(fusion, tr)
            d['revision_contre_exemple'] = dict(indice=premier, avant=[ok,n], induction=details,
                bascule_candidate=autre.bascule, apres=couverture)
            if couverture[0] == couverture[1]:
                th = fusion
        return th, info
    if contre_exemple:
        induction.induire = affiner
    m = MoteurC(budget=10, limite_plan=100000, theorie_precedente=prior)
    debut = time.monotonic()
    try:
        r = m.proposer(h)
    finally:
        transfert.transferer = original
        induction.induire = induction_originale
    d.update(duree=time.monotonic()-debut, infos=m.infos, plan=r[0] if r else None)
    d['memoire_source_inchangee'] = prior == prior_avant
    th = getattr(m, 'th_plan', None) or m.th_releve
    prog, non = exporter(th, m.tr.taille)
    d.update(but=repr(th.but), bascule=th.bascule, non_exporte=non)
    if r:
        d['theorie_exportee_conservee'] = (exporter(m.th_releve, m.tr.taille)[0] == r[1]
                                          and exporter(m.th_plan, m.tr.taille)[0] == r[1])
        assert d['theorie_exportee_conservee']
    c = Chaine(m, prog, h['grilles'], h['lots'], [], coups_deja_joues=prefixe)
    controle, etat = c.rejouer()
    d['controle_prefixe'] = controle
    d['etat_admissible'] = etat is not None
    if r:
        seq = [(a['action'], a['row'], a['col']) if a['action']=='MOUSE' else (a['action'],) for a in r[0]]
        d['adoption'] = c.adopter_plan(seq, origine='transfert_but_hypothese')
        d['verification_plan'] = c.verifier_plan(seq)
    # Même perception et théorie gelées ; aucune induction sur le suffixe.
    complet = Chaine(m, prog, gs, ls, [], coups_deja_joues=len(ls))
    d['controle_trace_complete_gelee'] = complet.rejouer()[0]
    sortie = racine / ('AUDIT_TRANSFERT_FT09_N3_MEMOIRE.json' if conserver else 'AUDIT_TRANSFERT_FT09_N3_FLAG_CORRIGE.json')
    if prefixe != 3:
        sortie = sortie.with_stem(sortie.stem + f'_PREFIXE{prefixe}')
    if contre_exemple:
        sortie = sortie.with_stem(sortie.stem + '_CONTRE_EXEMPLE')
    if not flag:
        sortie = sortie.with_stem(sortie.stem + '_SANS_FLAG')
    if not coherence:
        sortie = sortie.with_stem(sortie.stem + '_SOURCE_SYNCHRO')
    sortie.write_text(json.dumps(d, ensure_ascii=False, indent=2, default=str)+'\n')
    print(json.dumps({k:d.get(k) for k in ('duree','renommage','infos','plan','adoption','controle_prefixe','controle_trace_complete_gelee')}, default=str))

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--memoire', action='store_true')
    p.add_argument('--prefixe', type=int, default=3)
    p.add_argument('--contre-exemple', action='store_true')
    p.add_argument('--flag', type=int, choices=(0,1), default=1)
    p.add_argument('--coherence', type=int, choices=(0,1), default=1)
    a = p.parse_args()
    main(conserver=a.memoire, prefixe=a.prefixe, contre_exemple=a.contre_exemple, flag=a.flag, coherence=a.coherence)
