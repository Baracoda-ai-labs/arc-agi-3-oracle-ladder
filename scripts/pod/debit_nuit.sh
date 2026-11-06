#!/usr/bin/env bash
# SUR LE POD A (CW-222, chantier « débit ») : 1er essai apparié, moins de jetons par tour. Franzen v3 pur, 10 flux,
# 20 jeux non témoins, 48 min. Référence LOCAL_ANALYZER_MAX_OUTPUT=12288 (D0) contre 6144 (D1), seuls sur la carte,
# ordre ABBA (D0a D1a D1b D0b) contre la dérive. Démarre après la voie B ; un .cmd dans file_banc retient l'arrêt du pod.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
echo "until [ -f $W/bancs/debit.FINI ]; do sleep 60; done" > $W/bancs/file_banc/zz_attendre_debit.cmd
while pgrep -f creneau_voieB > /dev/null; do sleep 60; done
j "débit : début (voie B finie)"
for b in D0a:12288 D1a:6144 D1b:6144 D0b:12288; do
  n=${b%%:*}; m=${b##*:}
  j "débit : début $n (MAX_OUTPUT=$m)"
  cd $R && bash scripts/pod/bloc.sh $n LOCAL_ANALYZER_MAX_OUTPUT=$m MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
  j "débit : fin $n (code $?)"
done
touch $W/bancs/debit.FINI
