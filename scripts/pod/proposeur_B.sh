#!/usr/bin/env bash
# SUR LE POD A (CW-232, accord de Thomas 19/10 19 h 20) : sert Flash-Next, puis le proposeur du but de B sur le diagnostic
# (6 niveaux) et sur l'échantillon PuzzleScript (40 jeux, CCM-143-B). Plafond DUR : arrêt du pod 2 h après le lancement.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
( sleep 7200; j "plafond de 2 h (CW-232) : arrêt du pod"; touch $W/AUTORISE_ARRET; . $W/pod_env.sh 2>/dev/null; runpodctl stop pod "$RUNPOD_POD_ID" ) &
pgrep -f veille_inactivite.sh >/dev/null || nohup $W/veille_inactivite.sh >/dev/null 2>&1 &
j "proposeur B : démarrage du serveur"
if ! curl -sf http://127.0.0.1:8011/health >/dev/null; then
  touch $W/KEEPALIVE; cd $R && python3 scripts/pod/franzen_lanceur.py > $W/runs/lanceur.log 2>&1; rm -f $W/KEEPALIVE
fi
curl -sf http://127.0.0.1:8011/health >/dev/null || { j "proposeur B : serveur absent, arrêt"; touch $W/AUTORISE_ARRET; . $W/pod_env.sh 2>/dev/null; runpodctl stop pod "$RUNPOD_POD_ID"; exit 1; }
cd $R; P=$W/harnais/.venv/bin/python
j "proposeur B : diagnostic (6 niveaux)"
PYTHONPATH=$R:$W/pylib $P experiments/T3.8/proposeur_but.py $W/t4/environment_files --diag --serveur http://127.0.0.1:8011/v1 --modele flashnext > $W/runs/proposeur_diag.log 2>&1
j "proposeur B : PuzzleScript (40 jeux)"
PYTHONPATH=$R:$W/pylib $P experiments/T3.8/proposeur_but.py $W/t4/environment_files --ps 40 --serveur http://127.0.0.1:8011/v1 --modele flashnext > $W/runs/proposeur_ps.log 2>&1
j "proposeur B : fini"; touch $W/bancs/proposeur_B.FINI
