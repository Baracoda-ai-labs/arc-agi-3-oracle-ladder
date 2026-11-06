#!/usr/bin/env bash
# SUR LE POD A (CW-219, nuit du 18 au 19/10) : remplace banc_A2.sh (mixte et iw1 retirés de la file).
# compile_v2 (en cours) → paliers_v2 ; après le banc moteur seul (allumé + éteint) : étape 2 « rejeu » (diag_rejeu.py de C,
# 20 jeux non témoins, niveau 1, sans puis avec CHRYS_AMODAL) ; puis file ouverte ; tout fini + file vide 30 min → arrêt.
W=/workspace; R=$W/chrysalide3; F=$W/bancs/file_banc; P=$W/harnais/.venv/bin/python
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
until [ -f $W/bancs/banc_compile_v2.FINI ]; do sleep 60; done; j "banc : fin banc_compile_v2 ($(cat $W/bancs/banc_compile_v2.FINI))"
mv $R/experiments/T3.0/raw/plafond_P0_paliers.json $R/experiments/T3.0/raw/plafond_P0_paliers_echec_module.json 2>/dev/null
cd $R && LOT_VMEM_KO=16000000 bash scripts/pod/lancer_lot.sh banc_paliers_v2 env PYTHONPATH=$R:$R/experiments/T3.0:$W/pylib python experiments/T3.0/plafonds.py tous 1,2,3 1000000 600 4 paliers
until [ -f $W/bancs/moteur_seul.FINI ] && [ -f $W/bancs/moteur_seul_eteint.FINI ]; do sleep 60; done
for a in 0 1; do
  j "rejeu : début diag_rejeu AMODAL=$a"
  cd $R && CHRYS_AMODAL=$a PYTHONPATH=$R:$W/pylib nice -n 10 timeout 7200 $P experiments/T3.0/diag_rejeu.py 30 > $W/runs/diag_rejeu_amodal$a.log 2>&1
  mv $R/experiments/T3.0/raw/diag_rejeu.json $R/experiments/T3.0/raw/diag_rejeu_pod_amodal$a.json; j "rejeu : fin AMODAL=$a (code $?)"
done
touch $W/bancs/diag_rejeu.FINI
until [ -f $W/bancs/banc_paliers_v2.FINI ]; do sleep 60; done; j "banc : fin banc_paliers_v2 ($(cat $W/bancs/banc_paliers_v2.FINI))"
inactif=0
while [ $inactif -lt 30 ]; do
  c=$(ls $F/*.cmd 2>/dev/null | head -1)
  if [ -n "$c" ]; then n=$(basename "$c" .cmd); mv "$c" "$c.lance"; j "banc : début $n"
    cd $R && LOT_VMEM_KO=16000000 bash scripts/pod/lancer_lot.sh "$n" bash "$c.lance"; until [ -f $W/bancs/$n.FINI ]; do sleep 60; done
    j "banc : fin $n"; inactif=0
  else sleep 60; inactif=$((inactif+1)); fi
done
until [ -f $W/bancs/e4_n1_publics.FINI ] && { [ ! -f $W/bancs/e4_sansulimit.sh ] || [ -f $W/bancs/e4_sansulimit.FINI ]; } && ! pgrep -f creneau_voieB > /dev/null; do sleep 60; done
j "file vide depuis 30 min : arrêt du pod A (CW-186, CW-219)"; touch $W/AUTORISE_ARRET; . $W/pod_env.sh 2>/dev/null; runpodctl stop pod "$RUNPOD_POD_ID"
