"""104 T4 standards, N1 depuis RESET : même décideur, sans oracle ni source de jeu.

Un worker isolé par jeu, un seul actif, manifestes immuables et reprise sans
répéter les résultats terminés. Une sortie partielle exige une décision explicite.
"""
import argparse
import hashlib
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import time

R = Path(__file__).resolve().parent
RACINE_T4 = Path('/Users/ts/models/chrysalide3/experiments/T4/jeux/t4/environment_files').resolve()
INVENTAIRE = R/'INVENTAIRE_T4_CHAINE_NUIT.json'
INTEGRITE = R/'INTEGRITE_T4_SOURCES.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ecrire(path, objet):
    path = Path(path)
    temporaire = path.with_suffix(path.suffix+'.tmp')
    temporaire.write_text(json.dumps(objet,ensure_ascii=False,indent=2)+'\n')
    os.replace(temporaire,path)


def catalogue(inventaire=INVENTAIRE, racine=RACINE_T4):
    racine = Path(racine).resolve()
    j = json.loads(Path(inventaire).read_text())
    if racine != RACINE_T4 or Path(j['root']).resolve() != RACINE_T4:
        raise ValueError('Racine hors corpus T4 standard autorisé')
    rows = j['records']
    ids = [r['id'] for r in rows]
    if len(rows)!=104 or len(set(ids))!=104 or any(not (g.startswith('y') and g[1:].isdigit()) for g in ids):
        raise ValueError('Catalogue exact de104jeux T4 requis')
    if set(p.name for p in racine.iterdir() if p.is_dir()) != set(ids):
        raise ValueError('Répertoires du corpus différents du manifeste')
    for r in rows:
        if {p.name for p in (racine/r['id']).iterdir() if p.is_dir() and not p.name.startswith('__')} != {r['version']}:
            raise ValueError('Plusieurs versions ou version absente')
        p = racine/r['id']/r['version']/'metadata.json'
        if not p.resolve().is_relative_to(racine) or sha(p)!=r['metadata_sha256']:
            raise ValueError('Métadonnées absentes, déplacées ou modifiées')
        m = json.loads(p.read_text())
        if m['game_id'] != r['game_id'] or r['game_id'] != r['id']+'-'+r['version']:
            raise ValueError('Identité/version incohérente')
    return sorted(ids), rows


def sources():
    from boucle_agent_integree import empreintes
    h = empreintes()
    h[str(Path(__file__).resolve())] = sha(__file__)
    h[str(INVENTAIRE)] = sha(INVENTAIRE)
    return h


def agreger(out, ids):
    results = []
    for jeu in ids:
        p = out/jeu/'resultat_runner.json'
        if p.exists():
            results.append(json.loads(p.read_text()))
    resume = {'jeux_prevus':len(ids),'jeux_termines':len(results),'complet':len(results)==len(ids),
              'ordre':ids,'resultats':results,'niveaux_gagnes':sum(x.get('bilan',{}).get('niveaux_gagnes',0) for x in results),
              'coups_confirmes':sum(x.get('bilan',{}).get('coups_reels',0) for x in results),
              'appels_tentes':sum(x.get('bilan',{}).get('appels_step_tentes',0) for x in results),
              'initialisations_confirmees':sum(x.get('bilan',{}).get('initialisations',0) for x in results),
              'initialisations_tentees':sum(x.get('bilan',{}).get('initialisations_tentees',0) for x in results),
              'initialisations_tentees_inconnues':sum('initialisations_tentees' not in x.get('bilan',{}) for x in results),
              'incidents_coups_inconnus':sum(bool(x.get('coups_incident_inconnus')) for x in results)}
    ecrire(out/'resume.json',resume)
    return resume


def worker(args):
    ids,_ = catalogue(args.inventaire,args.racine)
    if args.worker not in ids:
        raise ValueError('Jeu absent du catalogue synthétique')
    from boucle_agent_integree import main
    main(argparse.Namespace(jeu=args.worker,sortie=args.sortie,coups=args.coups,
                            secondes=args.secondes,sans_reparation=False),
         dossier_jeux=args.racine,jeux_autorises=ids)


def executer_worker(cmd, log, timeout):
    # Le groupe appartient uniquement au worker créé ici, jamais à un processus trouvé.
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        return 'termine' if proc.wait(timeout=timeout)==0 else 'erreur_worker', proc.returncode
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        return 'timeout_superviseur', proc.returncode


def lancer(args):
    ids, rows = catalogue(args.inventaire,args.racine)
    if args.coups !=80 or args.secondes !=240:
        raise ValueError('Protocole104N1 figé à80coups/240secondes')
    out = args.sortie
    manifest = {'catalogue':rows,'ids':ids,'racine':str(args.racine.resolve()),
                'inventaire_sha256':sha(args.inventaire),'sources':sources(),
                'integrite_sources_environnements_sha256':sha(INTEGRITE) if INTEGRITE.exists() else None,
                'coups':args.coups,'secondes':args.secondes,'niveau':1,'initialisations_par_jeu':1,
                'workers':1,'oracle':False,'viabilite':'rapport historique, pas revérifiée',
                'comparaison':'banc technique synthétique, pas preuve de gain ARC'}
    if args.reprendre:
        ancien=json.loads((out/'manifeste.json').read_text())
        if ancien != manifest:
            raise ValueError('Reprise refusée : protocole, corpus ou sources ont changé')
    else:
        out.mkdir(parents=True,exist_ok=False)
        ecrire(out/'manifeste.json',manifest)
    resume=agreger(out,ids)
    if getattr(args,'preparer',False):
        print(json.dumps({'statut':'prepare_sans_sdk','jeux':len(ids),'sortie':str(out)}),flush=True)
        return resume
    for jeu in ids:
        destination=out/jeu
        if (destination/'resultat_runner.json').exists():
            continue  # Jamais rejouer un résultat terminal.
        if destination.exists() or (out/(jeu+'.stdout')).exists():
            raise ValueError(f'Sortie partielle {jeu} : reprise automatique interdite, conserver les coups')
        if sources()!=manifest['sources']:
            raise ValueError('Sources modifiées pendant campagne')
        cmd=[sys.executable,str(Path(__file__).resolve()),'--worker',jeu,'--sortie',str(destination),
             '--racine',str(args.racine),'--inventaire',str(args.inventaire),
             '--coups',str(args.coups),'--secondes',str(args.secondes)]
        ecrire(out/(jeu+'.commande.json'),{'commande':cmd,'debut_epoch':time.time()})
        debut=time.monotonic()
        with (out/(jeu+'.stdout')).open('x') as log:
            statut,code=executer_worker(cmd,log,args.secondes+15)
        destination.mkdir(exist_ok=True)
        p=destination/'bilan.json'
        try:
            bilan=json.loads(p.read_text()) if p.exists() else {}
        except (json.JSONDecodeError,OSError):
            bilan={}
            statut='bilan_incomplet'
        if not bilan and code==0:
            statut='bilan_absent'
        resultat={'jeu':jeu,'statut_runner':statut,'code':code,'wall_superviseur':time.monotonic()-debut,
                  'bilan':bilan,'coups_incident_inconnus':not bool(bilan),
                  'sources_conformes':sources()==manifest['sources']}
        ecrire(destination/'resultat_runner.json',resultat)
        resume=agreger(out,ids)
        print(json.dumps({'termine':jeu,'n':resume['jeux_termines'],'victoires':resume['niveaux_gagnes'],
                          'coups':resume['coups_confirmes'],'statut':statut}),flush=True)
    return agreger(out,ids)


def cli():
    p=argparse.ArgumentParser()
    p.add_argument('--sortie',type=Path,required=True)
    p.add_argument('--racine',type=Path,default=RACINE_T4)
    p.add_argument('--inventaire',type=Path,default=INVENTAIRE)
    p.add_argument('--coups',type=int,default=80)
    p.add_argument('--secondes',type=float,default=240)
    p.add_argument('--reprendre',action='store_true')
    p.add_argument('--preparer',action='store_true',help='Écrire manifeste et résumé, sans lancer de worker')
    p.add_argument('--worker')
    a=p.parse_args()
    if a.worker and (a.preparer or a.reprendre):
        p.error('--worker incompatible avec --preparer/--reprendre')
    worker(a) if a.worker else lancer(a)


if __name__=='__main__':
    cli()
