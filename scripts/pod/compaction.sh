#!/usr/bin/env bash
# SUR LE POD GPU (CW-263/264) : Franzen v3 pur, R0 contre R0 + COMPACTION (résumé glissant déjà dans le code de Franzen,
# éteint : ARC3_SUMMARY_INTERVAL_TOKENS=0). C1 = ARC3_SUMMARY_INTERVAL_TOKENS=29696 (moitié de ARC3_CONTEXT_DRAIN_TOKENS).
# 10 flux, 20 jeux non témoins, 48 min ; ordre ABBA (C0a C1a C1b C0b) ; minuterie d'arrêt : 4 h 15 après le lancement.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
[ "${SANS_ARRET:-0}" = "1" ] || ( sleep 15300; j "plafond de 4 h 15 (CW-264) : arrêt du pod"; touch $W/AUTORISE_ARRET; . $W/pod_env.sh 2>/dev/null; runpodctl stop pod "$RUNPOD_POD_ID" ) &
pgrep -f veille_inactivite.sh >/dev/null || nohup $W/veille_inactivite.sh >/dev/null 2>&1 &
for b in C0a:0 C1a:29696 C1b:29696 C0b:0; do
  n=${b%%:*}; m=${b##*:}
  j "compaction : début $n (ARC3_SUMMARY_INTERVAL_TOKENS=$m)"
  cd $R && bash scripts/pod/bloc.sh $n ARC3_SUMMARY_INTERVAL_TOKENS=$m MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
  j "compaction : fin $n (code $?)"
done
touch $W/bancs/compaction.FINI; j "compaction finie"
[ "${SANS_ARRET:-0}" = "1" ] || { j "arrêt du pod"; touch $W/AUTORISE_ARRET; . $W/pod_env.sh 2>/dev/null; runpodctl stop pod "$RUNPOD_POD_ID"; }
