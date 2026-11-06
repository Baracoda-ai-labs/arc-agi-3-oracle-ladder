#!/usr/bin/env bash
# SUR LE POD (CW-444 : jamais à vide) : après le bloc T (abba_T.FINI), passages R jusqu'au prochain bras (qui pose STOP_R).
W=/workspace
while [ ! -f $W/bancs/abba_T.FINI ]; do sleep 60; done
rm -f $W/bancs/STOP_R $W/bancs/r_attente.FINI
cd $W && R_DEBUT=${R_DEBUT:?R_DEBUT} bash $W/r_attente_run.sh
