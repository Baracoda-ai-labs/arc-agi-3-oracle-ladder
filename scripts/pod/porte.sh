#!/usr/bin/env bash
# SUR LE POD (CW-463/464, CCM-098-D) : après T4, la PORTE V4 (le moteur v4 du paquet v2 prend la main au début de chaque niveau,
# tant qu'il reconnaît et gagne ; sinon Franzen seul jusqu'à la fin du jeu). D'abord un ESSAI sur g50t seul (15 min) : il faut au
# moins une ligne porte_v4 « victoire » dans la trace (attendu de F : 7 niveaux). Si l'essai passe → ABBA P contre R (abba_franzen.sh,
# 4 paires) ; sinon → passages R d'attente (le bras 3 est arrêté, CW-471), pour que le pod ne soit jamais à vide.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') porte : $*" | tee -a $W/runs/chaine_etapes.txt; }
PAQ=$R/experiments/GEL27_moteur_seul_v2
DP="CHRYS_PORTE_V4=1 CHRYS_PORTE_V4_PAQUET=$PAQ CHRYS_GARDE_MUR_S=1800"
while [ ! -f $W/bancs/abba_T.FINI ]; do sleep 30; done
[ "$(cat $W/P_head.txt)" = "715d1eba" ] || { j "P_head.txt inattendu : ARRÊT"; exit 1; }
tar xzf $W/P_head.tgz -C $R && j "code du pod mis à jour (715d1eba, porte v4)"
python3 $R/scripts/arc3/patcher_franzen.py $W/harnais > /dev/null && python3 $R/scripts/arc3/patcher_garde.py $W/harnais > /dev/null \
  && j "patchs franzen et garde : OK" || { j "patchs en échec"; ESSAI=0; }
python3 - $R/chrysalide/arc3/porte_v4.py $W/harnais/inference/chrysalide_arc3/porte_v4.py <<'PY2' && j "porte_v4.py du harnais = dépôt (imports réécrits)" || { j "porte_v4.py du harnais ≠ dépôt"; ESSAI=0; }
import sys
a = open(sys.argv[1]).read().replace("from chrysalide.arc3.", "from inference.chrysalide_arc3.").replace("from chrysalide.arc3 import", "from inference.chrysalide_arc3 import")
sys.exit(open(sys.argv[2]).read() != a)
PY2
[ -f $PAQ/EMPREINTE.txt ] || { j "paquet v2 absent"; ESSAI=0; }
if [ "${ESSAI:-1}" = 1 ]; then
  j "essai PG0 : g50t seul, porte v4, 15 min"
  cd $R && bash scripts/pod/bloc.sh PG0 $DP ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=15 -- '["g50t"]' > $W/runs/PG0.log 2>&1 < /dev/null
  n=$(zcat -f $W/runs/PG0/chrysalide/g50t*_trace.jsonl* 2>/dev/null | grep '"porte_v4"' | grep -c '"victoire": true')
  e=$(grep -c "repli Franzen\|Traceback" $W/runs/PG0/2026*/stdout.log 2>/dev/null)
  j "essai PG0 : $n victoire(s) de la porte, $e erreur(s) de garde"
  [ "$n" -ge 1 ] && [ "$e" = 0 ] && OK=1
fi
if [ "${OK:-0}" = 1 ]; then
  j "ESSAI OK → ABBA porte v4 (P) contre R"
  cd $W && PREFIXE=P HEAD_C=715d1eba DRAPEAUX="$DP" R_DEBUT=32 ATTENDRE=abba_T.FINI bash $W/abba_franzen_run.sh > $W/runs/abba_P.log 2>&1 < /dev/null
  j "ABBA porte v4 fini → passages R d'attente"
  rm -f $W/bancs/STOP_R $W/bancs/r_attente.FINI
  cd $W && R_DEBUT=36 bash $W/r_attente_run.sh
else
  j "ESSAI KO ou contrôle en échec → passages R d'attente (bras 3 arrêté par Thomas, CW-471)"
  rm -f $W/bancs/STOP_R $W/bancs/r_attente.FINI
  cd $W && R_DEBUT=32 bash $W/r_attente_run.sh
fi
