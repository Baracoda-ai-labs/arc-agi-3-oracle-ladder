#!/usr/bin/env bash
# SUR LE POD (CW-368, Thomas 21/10 22 h) : la nuit bascule sur NEXTN dès la fin du passage M0/R en cours (STOP_M posé à 21 h 43).
# Met à jour le code du pod (/workspace/i_head.tgz, qui contient SGL_SPEC_STEPS dans franzen_lanceur.py), puis lance nextn.sh
# (blocs ABBA A/B jusqu'à STOP_N). Franzen seul : les patchs du harnais (code de 15 h 34) ne servent pas, CHRYS_* éteints.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
while [ ! -f $W/bancs/m0r_nuit.FINI ]; do sleep 30; done
tar xzf $W/i_head.tgz -C $R && j "nuit_nextn : code du pod mis à jour ($(cat $W/i_head.txt))"
grep -q SGL_SPEC_STEPS $R/scripts/pod/franzen_lanceur.py || { j "nuit_nextn : lanceur sans SGL_SPEC_STEPS : ARRÊT (repli M0/R à faire à la main)"; exit 1; }
j "nuit_nextn : départ de NEXTN (CW-368)"
NEXTN_DEBUT=1 bash $W/nextn_run.sh
