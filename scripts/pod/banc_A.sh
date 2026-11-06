#!/usr/bin/env bash
# SUR LE POD A (CW-186) : BANC D'AMÉLIORATION DU MOTEUR. File : P0 « largeur » avec préfixes (en cours) → mixte → iw1
# (versions de C, CCM-066-C), même banc P0 (1 000 000 nœuds, 600 s, 6 processus). Ensuite, toute nouvelle version déposée
# dans /workspace/bancs/file_banc/<nom>.cmd (une commande par fichier) est lancée ; rien en file pendant 30 min → arrêt.
W=/workspace; R=$W/chrysalide3; F=$W/bancs/file_banc
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
mkdir -p $F
lot() {  # nom, recherche — 4 processus × 16 Go (18/10 : MemoryError à 6 Go sur compile, mixte, iw1)
  cd $R && LOT_VMEM_KO=16000000 bash scripts/pod/lancer_lot.sh "$1" env PYTHONPATH=$R:$R/experiments/T3.0:$W/pylib python experiments/T3.0/plafonds.py tous 1,2,3 1000000 600 4 "$2"
  until [ -f $W/bancs/$1.FINI ]; do sleep 60; done; j "banc : fin $1 ($(cat $W/bancs/$1.FINI))"
}
# CCM-123-B : règles complétées (victoires des 7 programmes) → la référence `largeur` est RECALCULÉE en tête de file
lot banc_largeur_v2 largeur
lot banc_but but
lot banc_compile compile   # CW-198 (1) : compilateur d'état de C (6aabc48), avant mixte et iw1
lot banc_mixte mixte
lot banc_iw1 iw1
inactif=0
while [ $inactif -lt 30 ]; do
  c=$(ls $F/*.cmd 2>/dev/null | head -1)
  if [ -n "$c" ]; then n=$(basename "$c" .cmd); mv "$c" "$c.lance"; j "banc : début $n"
    cd $R && bash scripts/pod/lancer_lot.sh "$n" bash "$c.lance"; until [ -f $W/bancs/$n.FINI ]; do sleep 60; done
    j "banc : fin $n"; inactif=0
  else sleep 60; inactif=$((inactif+1)); fi
done
until [ -f $W/bancs/e4_n1_publics.FINI ] && { [ ! -f $W/bancs/e4_relance16.sh ] || [ -f $W/bancs/e4_relance16.FINI ]; }; do sleep 60; done
j "banc vide depuis 30 min : arrêt du pod A (CW-186)"; touch $W/AUTORISE_ARRET; . $W/pod_env.sh 2>/dev/null; runpodctl stop pod "$RUNPOD_POD_ID"
