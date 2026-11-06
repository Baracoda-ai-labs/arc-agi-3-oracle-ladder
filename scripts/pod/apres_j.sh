#!/usr/bin/env bash
# SUR LE POD (CW-424) : X est suspendu (bogue de relève). Après J4 (bancs/ip.FINI), le GPU fait des passages R (r_attente.sh) jusqu'à
# STOP_R ; x.sh, relancé avec le SHA corrigé, pose STOP_R et attend r_attente.FINI avant de partir.
W=/workspace
while [ ! -f $W/bancs/ip.FINI ]; do sleep 30; done
cd $W && R_DEBUT=${R_DEBUT:?R_DEBUT} bash $W/r_attente_run.sh
