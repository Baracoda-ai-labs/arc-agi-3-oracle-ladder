#!/usr/bin/env bash
# SUR LE POD (CW-420) : I′ = 4 paires seulement. Pose bancs/STOP_J dès le début de J4 → ip.sh s'arrête après J4 (STOP_J lu avant
# chaque passage), puis la relève X peut partir. Ne modifie pas ip.sh en cours d'exécution (bash lit le script au fil de l'eau).
W=/workspace
until grep -q "ip : début J4" $W/runs/chaine_etapes.txt; do sleep 60; done
touch $W/bancs/STOP_J; echo "$(date '+%d/%m %H:%M') A : STOP_J posé au début de J4 (CW-420 : 4 paires)" >> $W/runs/chaine_etapes.txt
