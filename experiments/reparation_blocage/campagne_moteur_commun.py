"""Campagne séquentielle du pilote existant, sans snapshot propre au jeu en entrée.

Les quotas supervisés sont échantillonnés ; un arrêt de budget n'est pas une défaite.
L'attribution cf2a1f81 reste non évaluable : ne pas utiliser critere_gel_458 directement.
"""
import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import queue
import signal
import subprocess
import sys
import threading
import time

R = Path(__file__).resolve().parent
INTERDITS = {'cn04','s5i5','tu93','vc33','wa30'}
LIMITES = ('actions_jeu','actions_niveau','mur_jeu_s','mur_commande_s','cpu_jeu_s')


def autorises():
    # Lire le registre existant sans importer moteur/SDK ni explorer les jeux.
    arbre=ast.parse((R/'boucle_agent_integree.py').read_text())
    for n in arbre.body:
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='AUTORISES' for t in n.targets):
            return set(ast.literal_eval(n.value))
    raise ValueError('Registre AUTORISES absent')


def valider(m):
    champs={'version','jeux','graines','limites','composition_contextuelle_auto','reprises','memoire_inter_jeux','recherche_prolongee','recherche_workers'}
    if m.get('version')==3:champs.add('portee')
    if set(m)!=champs or m['version'] not in (2,3):raise ValueError('Schéma manifeste invalide')
    portee=m.get('portee','multi_niveaux')
    if portee not in ('n1','multi_niveaux'):raise ValueError('Portée inconnue')
    if not isinstance(m['jeux'],list) or not m['jeux'] or len(set(m['jeux']))!=len(m['jeux']):raise ValueError('Jeux uniques requis')
    if set(m['jeux']) & INTERDITS or not set(m['jeux']) <= autorises():raise ValueError('Jeu non autorisé ou témoin')
    if m['jeux']!=sorted(m['jeux']):raise ValueError('Ordre alphabétique requis')
    if m['graines']!=([0] if portee=='n1' else [0,1]):raise ValueError('Graines incompatibles avec la portée')
    if set(m['limites'])!=set(LIMITES):raise ValueError('Limites explicites requises')
    for k,v in m['limites'].items():
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not 0<v<float('inf'):raise ValueError('Budget non fixé : '+k)
    for k in ('actions_jeu','actions_niveau'):
        if not isinstance(m['limites'][k],int) or m['limites'][k]<8:raise ValueError('Quota actions entier >=8 (acquisition initiale)')
    for k in ('composition_contextuelle_auto','reprises','recherche_prolongee'):
        if not isinstance(m[k],bool):raise ValueError('Drapeau booléen requis')
    if type(m['recherche_workers']) is not int or m['recherche_workers'] not in (1,2):
        raise ValueError('Un ou deux workers de recherche requis')
    if m['memoire_inter_jeux']!='aucune':raise ValueError('Mémoire interjeux non implémentée')
    return m


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def versions():
    resultat={}
    for nom in ('numpy','arc-agi','arcengine','cloudpickle','clingo'):
        try:resultat[nom]=importlib.metadata.version(nom)
        except importlib.metadata.PackageNotFoundError:resultat[nom]=None
    return resultat


def sources():
    from attestation_moteur_commun import inventaire
    return inventaire(R)


def cpu_groupe(pgid, historique):
    """CPU cumulés des processus encore visibles ; précision de ps à la seconde."""
    texte=subprocess.check_output(['ps','-axo','pid=,pgid=,time='],text=True)
    for ligne in texte.splitlines():
        pid,groupe,chrono=ligne.split()
        if int(groupe)!=pgid:continue
        jours,sep,chrono=chrono.rpartition('-'); jours=int(jours) if sep else 0
        parts=list(map(float,chrono.split(':')))
        historique[pid]=max(historique.get(pid,0),jours*86400+sum(v*60**i for i,v in enumerate(reversed(parts))))
    return sum(historique.values())


def etat(path):
    try:return json.loads(path.read_text())
    except (FileNotFoundError,json.JSONDecodeError):return {}


def niveaux(dossier):
    result={}
    for p in sorted(dossier.rglob('partie.json')):
        if not p.parent.name.startswith(('N','tentative_')):continue
        parents=[x.name for x in p.parents if x.name.startswith('N') and x.name[1:].isdigit()]
        if not parents:continue
        niveau=int(parents[0][1:]);j=json.loads(p.read_text());rows=j.get('rows',[])
        d=result.setdefault(niveau,dict(niveau=niveau,victoire=False,coups=0,resets=0,defaites=0,gagnant=None,attribution='non_evaluable'))
        d['coups']+=len(rows)
        d['resets']+=sum(r.get('action')==0 for r in rows)
        d['defaites']+=sum(str(r.get('state','')).endswith('GAME_OVER') for r in rows)
        d['victoire'] |= any(r.get('levels_completed',0)>=niveau for r in rows)
    return list(result.values())


def commande(jeu,graine,sortie,m):
    c=[sys.executable,'-B',str(R/'session_chaine_generique.py'),'--jeu',jeu,'--neuf','--graine',str(graine),'--sortie',str(sortie)]
    if m['composition_contextuelle_auto']:c.append('--composition-contextuelle-auto')
    if m['recherche_prolongee']:c.append('--recherche-prolongee')
    c.extend(['--recherche-workers',str(m['recherche_workers'])])
    return c


def executer(jeu,graine,out,m):
    session=out/'session';out.mkdir(parents=True,exist_ok=False)
    env={k:v for k,v in os.environ.items() if not k.startswith('CHRYS_') and k!='GEL27_TEMOINS'}
    env.update(PYTHONPATH='.:livraison_p1/code:..',PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='0')
    cmd=commande(jeu,graine,session,m)
    from attestation_moteur_commun import construire, verifier
    attestation=construire(R,env=env)
    (out/'attestation_avant.json').write_text(json.dumps(attestation,indent=2))
    (out/'commande.json').write_text(json.dumps({'argv':cmd,'cwd':str(R/'paquet'),'env':{k:env[k] for k in ('PYTHONPATH','PYTHONHASHSEED','PYTHONDONTWRITEBYTECODE')}},indent=2))
    lim=m['limites'];debut=time.monotonic();q=queue.Queue();statut='demarrage';cpu_max=0;cpu_processus={}
    with (out/'stderr.log').open('w') as err, (out/'stdout.log').open('w') as log:
        p=subprocess.Popen(cmd,cwd=R/'paquet',env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,start_new_session=True)
        def lire():
            for line in p.stdout:
                log.write(line);log.flush()
                try:q.put(json.loads(line))
                except json.JSONDecodeError:pass
            q.put(None)
        thread=threading.Thread(target=lire,daemon=True);thread.start();commande_debut=debut
        try:
            while True:
                courant=etat(session/'etat.json')
                cpu_max=max(cpu_max,cpu_groupe(p.pid,cpu_processus),courant.get('cpu_total_recolte_s',0))
                maintenant=time.monotonic()
                if maintenant-debut>=lim['mur_jeu_s'] or maintenant-commande_debut>=lim['mur_commande_s'] or cpu_max>=lim['cpu_jeu_s']:
                    statut='budget_calcul_interrompu';break
                try:r=q.get(timeout=.2)
                except queue.Empty:continue
                if r is None:statut='processus_termine';break
                if 'statut' not in r:continue
                if r.get('jeu_gagne'):statut='jeu_gagne';break
                if m.get('portee')=='n1' and (r.get('niveaux_gagnes',0)>=1 or r['statut']=='niveau_gagne'):
                    statut='n1_gagne_arret_protocole';break
                if r['statut'] in ('diagnostic_requis','reset_niveau_inattendu'):
                    statut=r['statut'];break
                comptes=niveaux(session);n=r.get('niveau',1)
                compte=0 if r['statut']=='niveau_gagne' else sum(x['coups'] for x in comptes if x['niveau']==n)
                reserve=2 if r['statut']=='defaite_sdk' and m['reprises'] else 1
                if r.get('coups_reels',0)+reserve>lim['actions_jeu'] or compte+reserve>lim['actions_niveau']:
                    statut='budget_actions_atteint';break
                if r['statut'] not in ('prete_nouvelle_boucle','lot_termine_session_conservee','auto_lots_termines_session_conservee','niveau_gagne','defaite_sdk','en_cours'):
                    statut=r['statut'];break
                if r['statut']=='defaite_sdk' and not m['reprises']:statut='defaite_sdk';break
                p.stdin.write(json.dumps({'op':'auto','lots':1,'coups':1,'reprises':m['reprises']})+'\n');p.stdin.flush();commande_debut=time.monotonic()
        finally:
            if p.poll() is None:
                if not statut.endswith('interrompu'):
                    try:p.stdin.write('{"op":"close"}\n');p.stdin.flush();p.wait(timeout=5)
                    except (BrokenPipeError,subprocess.TimeoutExpired):pass
                if p.poll() is None:
                    os.killpg(p.pid,signal.SIGTERM)
                    try:p.wait(timeout=3)
                    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
            thread.join(timeout=2)
    lignes=niveaux(session);e=etat(session/'etat.json')
    declarations=etat(session/'sources.json') or None
    controle_sources=verifier(attestation,declarations)
    (out/'attestation_apres.json').write_text(json.dumps(controle_sources,indent=2))
    from export_attribution_commune import exporter
    incomplet=statut=='budget_calcul_interrompu' or p.returncode!=0
    comptes_alignés=bool(e) and e.get('coups_reels')==sum(x['coups'] for x in lignes)
    lignes, attribution=exporter(out,lignes,interruption=incomplet or not comptes_alignés)
    (out/'resultat.json').write_text(json.dumps(lignes,indent=2))
    bilan={'statut':statut,'returncode':p.returncode,'mur_s':time.monotonic()-debut,'cpu_observe_max_s':cpu_max,
        'cpu_statut':'borne_inferieure_echantillonnee_non_comptable','initialisations':e.get('initialisations'),
        'attestation_sources':controle_sources['statut'],'fermeture_imports_complete':False,
        'coups_reels':sum(x['coups'] for x in lignes),'attribution_cf2a1f81':attribution['attribution_cf2a1f81'],
        'comptage_aligne_etat':comptes_alignés,
        'appel_final_potentiellement_incomplet':statut=='budget_calcul_interrompu' or p.returncode!=0,
        'critere_gel_458':('non_calcule_exiger_evaluable_avant_comparaison' if not attribution['manques'] else
                          'interdit_preuves_intervention_incompletes'),'etat_final':e}
    (out/'bilan.json').write_text(json.dumps(bilan,indent=2));return bilan


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--protocole',type=Path,required=True);ap.add_argument('--sortie',type=Path,required=True)
    ap.add_argument('--verifier-seulement',action='store_true');a=ap.parse_args();m=valider(json.loads(a.protocole.read_text()))
    if a.verifier_seulement:print('Manifeste valide ; aucun SDK lancé');return
    a.sortie.mkdir(parents=True,exist_ok=False);empreintes=sources()
    meta={'protocole':m,'sources':empreintes,'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),
        'python':sys.version,'executable':sys.executable,'executable_sha256':sha(sys.executable),
        'dependances':versions(),'plateforme':platform.platform(),'memoire_inter_jeux':'aucune','attribution':'non_evaluable'}
    (a.sortie/'manifeste.json').write_text(json.dumps(meta,indent=2));resultats={}
    for graine in m['graines']:
        for jeu in m['jeux']:
            if sources()!=empreintes:raise RuntimeError('Sources modifiées : campagne interrompue')
            resultats[f'{graine}/{jeu}']=executer(jeu,graine,a.sortie/f'graine_{graine}'/jeu,m)
            (a.sortie/'resume.json').write_text(json.dumps(resultats,indent=2))
            if sources()!=empreintes:raise RuntimeError('Sources modifiées pendant le jeu : résultat non figé')

if __name__=='__main__':main()
