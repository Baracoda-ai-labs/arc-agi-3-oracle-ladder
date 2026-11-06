"""Cherche une expérience terminale entre buts concurrents, sans SDK ni induction."""
import argparse
import copy
import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path
import cloudpickle
import numpy as np
from buts_modele_conserve import actions_modele
from extension_but_relationnel import proposer
from contexte_export import exporter_contextuel
from chaine_coherente import Chaine
from chrysalide.arc3.moteur import _lot_c, _candidats_buts
from chrysalide.arc3.logique.plan import planifier, distance_but
from chrysalide.arc3.logique.theorie import Theorie
from chrysalide.arc3.langage import Programme
from chrysalide.arc3.sim_rapide import ProgrammeCompile
from chrysalide.arc3.logique.plan_langage import cle_complete


def chercher(snapshot, sortie, secondes=120):
    payload = snapshot.read_bytes()
    meta = json.loads(snapshot.with_suffix('.json').read_text())
    sha = hashlib.sha256(payload).hexdigest()
    assert sha == meta['sha256']
    agent = cloudpickle.loads(payload)
    assert hashlib.sha256(np.asarray(agent.images[-1], dtype=np.int16).tobytes()).hexdigest() == meta['image_sha256']
    source = next(iter(agent.chaines.values()))
    th = copy.deepcopy(source.perception.th_releve)
    tr = copy.copy(source.perception.tr)
    tr.etats = list(tr.etats[:len(source.grilles)])
    tr.etats += [tr.etat(g) for g in source.grilles[len(tr.etats):]]
    extensions, preuves = proposer(th, tr, source.grilles)
    admis = _candidats_buts(replace(th, buts_motifs=[*th.buts_motifs, *extensions]), tr)
    buts = [b for b in extensions if b in admis]
    assert len(buts) > 1
    controle, courant = source.rejouer()
    assert courant is not None
    pc0, scene0 = courant
    monde0 = tr.etat(agent.images[-1])
    actions = actions_modele(source, [6])
    codes = [tr.action_cases(('clic', a[2], a[1])) for a in actions if a[0] == 'MOUSE']
    physique = replace(th, but=None)
    texte, non = exporter_contextuel(source.perception, physique, tr.taille)
    assert not non
    rapport = dict(snapshot=str(snapshot), sha256=sha, observations=len(agent.actions),
        buts=buts, preuves=preuves, actions_sdk=0, recherche='planificateur_theorie_existant',
        budget_cpu_recherche=secondes, essais=[], plan=None, experience_validee=False)
    debut = time.process_time()
    # Même mécanisme pour tous les buts ; ordre au nombre de contraintes violées.
    ordre = sorted(buts, key=lambda b: distance_but(replace(th, but=b), monde0))
    for i, but in enumerate(ordre):
        budget = max(0, (secondes-(time.process_time()-debut))/(len(ordre)-i))
        if budget <= 0: break
        t = time.process_time(); mur = time.monotonic()
        theorie = replace(th, but=but)
        seq, noeuds = planifier(theorie, monde0, tr.taille, codes, limite=200000,
                               deadline=t+budget, guide=True)
        essai = dict(but=but, distance_initiale=distance_but(theorie, monde0),
            cpu_s=time.process_time()-t, mur_s=time.monotonic()-mur,
            noeuds=noeuds, budget_cpu=budget, plan_trouve=bool(seq))
        rapport['essais'].append(essai)
        if seq:
            plan = [Chaine.action_tuple(_lot_c(a, tr)) for a in seq]
            pi, pc = Programme(texte), ProgrammeCompile(texte)
            pi.etat = copy.deepcopy(pc0.etat); pc.etat = copy.deepcopy(pc0.etat)
            pc._ref.etat = pc.etat
            si, sc = copy.deepcopy(scene0), copy.deepcopy(scene0)
            monde = monde0; predictions = []
            for k, (code, action) in enumerate(zip(seq, plan), 1):
                monde, _ = physique.pas(monde, code, tr.taille)
                pi.step(si, action); pc.step(sc, action)
                assert cle_complete(si, pi.etat) == cle_complete(sc, pc.etat)
                assert np.array_equal(source.perception.rendu(sc),
                                      source.perception._masquer(physique.rendu(monde, tr.taille, tr.fond)))
                vrais = [j for j,b in enumerate(buts) if Theorie._vrai(b, monde)]
                predictions.append(dict(pas=k, buts_vrais=vrais,
                    image_sha256=hashlib.sha256(np.asarray(source.perception.rendu(sc),dtype=np.int16).tobytes()).hexdigest()))
                if 0 < len(vrais) < len(buts):
                    rapport.update(plan=plan[:k], predictions=predictions,
                        buts_predisant_victoire=vrais,
                        buts_predisant_continue=[j for j in range(len(buts)) if j not in vrais],
                        experience_validee=True, dynamique_interprete_compile_identiques=True)
                    break
        rapport['cpu_recherche_et_validation_s'] = time.process_time()-debut
        sortie.write_text(json.dumps(rapport, indent=2, default=int))
        print(json.dumps({'essai':essai,'experience_validee':rapport['experience_validee']},default=int),flush=True)
        if rapport['experience_validee']: break
    assert snapshot.read_bytes() == payload
    rapport['snapshot_inchange'] = True
    rapport['limite'] = 'Predictions dans hypotheses seulement ; absence de plan au budget ne prouve pas impossibilite.'
    sortie.write_text(json.dumps(rapport, indent=2, default=int))
    return rapport


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--sortie',type=Path,required=True);p.add_argument('--secondes',type=float,default=120)
    a=p.parse_args();chercher(a.snapshot,a.sortie,a.secondes)
