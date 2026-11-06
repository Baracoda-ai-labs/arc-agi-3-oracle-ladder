#!/usr/bin/env bash
# SUR LE POD (CW-408) : après la reprise du matin. Le disque du conteneur est remis à neuf à chaque arrêt (seul /workspace reste) :
# installation idempotente (setup_franzen.sh : pkg-config, uv, venv du harnais), serveur de Franzen (franzen_lanceur.py recrée
# /tmp/sgl-intel depuis out-penny), puis arrêt du soir armé à 18:00 UTC (20 h Paris). La file de mesures du jour est lancée à part,
# par la session A, d'après CANAL.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') jour : $*" | tee -a $W/runs/chaine_etapes.txt; }
j "démarrage (reprise du pod)"
cd $R && bash scripts/pod/setup_franzen.sh > $W/runs/setup_jour.log 2>&1 && j "installation OK" || { j "installation ÉCHEC (setup_jour.log)"; }
(cd $R && python3 scripts/pod/franzen_lanceur.py > $W/runs/lanceur_jour.log 2>&1)
curl -sf http://127.0.0.1:8011/health >/dev/null && j "serveur prêt" || j "serveur ABSENT (lanceur_jour.log)"
nohup bash $R/scripts/pod/arret_soir.sh > /dev/null 2>&1 < /dev/null &
j "arrêt du soir armé (18:00 UTC)"
