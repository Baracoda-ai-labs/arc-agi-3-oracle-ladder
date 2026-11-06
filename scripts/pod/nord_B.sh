#!/usr/bin/env bash
# SUR LE POD B (CW-127) : file « nord ». 1) attendre la fin de l'installation ; 2) lever le serveur Flash-Next (10 requêtes) ;
# 3) P1-b : test de format de B (Flash-Next écrit les règles), 50 min au plus. Journal : /workspace/bancs/nord_B.log
W=/workspace; cd $W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/bancs/nord_etapes.txt; }
until [ -x $W/harnais/.venv/bin/python ] && ! pgrep -f setup_franzen >/dev/null; do sleep 30; done
j "installation finie"
touch $W/KEEPALIVE
python3 scripts/pod/franzen_lanceur.py > $W/bancs/lanceur.log 2>&1
rm -f $W/KEEPALIVE
curl -sf http://127.0.0.1:8011/health >/dev/null || { j "serveur absent : arrêt de la file"; exit 1; }
j "serveur prêt ; début P1-b (test de format)"
mkdir -p $W/chrysalide3/experiments/arc3 && [ -e $W/chrysalide3/experiments/arc3/environment_files ] || ln -s $W/environment_files $W/chrysalide3/experiments/arc3/environment_files
cd $W/chrysalide3 && timeout 3000 env PYTHONPATH=$W/chrysalide3 PY=$W/harnais/.venv/bin/python bash experiments/T3.3/creneau_llm.sh > $W/bancs/creneau_llm.log 2>&1
j "fin P1-b (code $?)"
