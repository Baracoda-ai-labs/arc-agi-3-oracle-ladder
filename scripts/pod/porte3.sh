#!/usr/bin/env bash
# RELANCE 3 (24/10 matin, A, CCM-404-A) : correctif du verrou c142f486 ; essai à 10 JEUX SIMULTANÉS (et non g50t seul : P1 a
# montré que l'essai à 1 jeu ne voit pas les conflits entre fils). 4 paires NEUVES (bras V), R d'attente arrêtés d'abord.
# Texte d'origine : (CW-463/464, CCM-098-D) après T4, la PORTE V4 (le moteur v4 du paquet v2 prend la main au début de chaque niveau,
# tant qu'il reconnaît et gagne ; sinon Franzen seul jusqu'à la fin du jeu). D'abord un ESSAI sur g50t seul (15 min) : il faut au
# moins une ligne porte_v4 « victoire » dans la trace (attendu de F : 7 niveaux). Si l'essai passe → ABBA P contre R (abba_franzen.sh,
# 4 paires) ; sinon → passages R d'attente (le bras 3 est arrêté, CW-471), pour que le pod ne soit jamais à vide.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') porte : $*" | tee -a $W/runs/chaine_etapes.txt; }
PAQ=$R/experiments/GEL27_moteur_seul_v2
DP="CHRYS_PORTE_V4=1 CHRYS_PORTE_V4_PAQUET=$PAQ CHRYS_GARDE_MUR_S=1800"
if pgrep -f r_attente_run.sh >/dev/null; then touch $W/bancs/STOP_R; while [ ! -f $W/bancs/r_attente.FINI ]; do sleep 30; done; fi
[ "$(cat $W/V_head.txt)" = "c142f486" ] || { j "V_head.txt inattendu : ARRÊT"; exit 1; }
tar xzf $W/V_head.tgz -C $R && j "code du pod mis à jour (c142f486, porte v4 + verrou)"
python3 $R/scripts/arc3/patcher_franzen.py $W/harnais > /dev/null && python3 $R/scripts/arc3/patcher_garde.py $W/harnais > /dev/null \
  && j "patchs franzen et garde : OK" || { j "patchs en échec"; ESSAI=0; }
python3 - $R/chrysalide/arc3/porte_v4.py $W/harnais/inference/chrysalide_arc3/porte_v4.py <<'PY2' && j "porte_v4.py du harnais = dépôt (imports réécrits)" || { j "porte_v4.py du harnais ≠ dépôt"; ESSAI=0; }
import sys
a = open(sys.argv[1]).read().replace("from chrysalide.arc3.", "from inference.chrysalide_arc3.").replace("from chrysalide.arc3 import", "from inference.chrysalide_arc3 import")
sys.exit(open(sys.argv[2]).read() != a)
PY2
[ -f $PAQ/EMPREINTE.txt ] || { j "paquet v2 absent"; ESSAI=0; }
if [ "${ESSAI:-1}" = 1 ]; then
  grep -q "_VERROU = threading.Lock()" $R/chrysalide/arc3/porte_v4.py || { j "verrou absent du code : ARRÊT de l'essai"; ESSAI=0; }
fi
if [ "${ESSAI:-1}" = 1 ]; then
  j "essai PV0 : 10 jeux simultanés (g50t, ka59 + 8), porte v4 + verrou, 15 min"
  cd $R && bash scripts/pod/bloc.sh PV0 $DP ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=15 \
    -- '["g50t","ka59","ft09","ls20","cd82","ar25","sp80","m0r0","re86","tr87"]' > $W/runs/PV0.log 2>&1 < /dev/null
  n=$(zcat -f $W/runs/PV0/chrysalide/g50t*_trace.jsonl* 2>/dev/null | grep '"porte_v4"' | grep -c '"victoire": true')
  x=$(zcat -f $W/runs/PV0/chrysalide/*_trace.jsonl* 2>/dev/null | grep '"porte_v4"' | grep -c '"raison": "erreur')
  f=$(zcat -f $W/runs/PV0/chrysalide/*_trace.jsonl* 2>/dev/null | grep '"porte_v4"' | grep -c '"fin"')
  e=$(grep -c "repli Franzen\|Traceback" $W/runs/PV0/2026*/stdout.log 2>/dev/null)
  j "essai PV0 : g50t $n victoire(s), $x porte(s) en erreur, $f porte(s) finies sur 10, $e repli(s)"
  [ "$n" -ge 5 ] && [ "$x" = 0 ] && [ "$f" -ge 9 ] && [ "$e" = 0 ] && OK=1
fi
if [ "${OK:-0}" = 1 ]; then
  j "ESSAI OK → ABBA porte v4 + verrou (V, 4 paires neuves) contre R"
  cd $W && PREFIXE=V HEAD_C=c142f486 DRAPEAUX="$DP" R_DEBUT=${R_V:?R_V} ATTENDRE=r_attente.FINI bash $W/abba_franzen_run.sh > $W/runs/abba_V.log 2>&1 < /dev/null
  j "ABBA porte v4 fini → passages R d'attente"
  rm -f $W/bancs/STOP_R $W/bancs/r_attente.FINI
  cd $W && R_DEBUT=$((R_V + 4)) bash $W/r_attente_run.sh
else
  j "ESSAI KO ou contrôle en échec → passages R d'attente (bras 3 arrêté par Thomas, CW-471)"
  rm -f $W/bancs/STOP_R $W/bancs/r_attente.FINI
  cd $W && R_DEBUT=${R_V} bash $W/r_attente_run.sh
fi
