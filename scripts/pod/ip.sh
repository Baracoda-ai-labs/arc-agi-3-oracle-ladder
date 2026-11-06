#!/usr/bin/env bash
# SUR LE POD (CW-412, jalon 1 : samedi 24 au soir) : I′ (options corrigées par D selon CCM-356-A : « but supposé » au lieu de
# « reaches goal » sans but confirmé ; aucune option annoncée quand elle est vide) contre R (Franzen seul), appariés par blocs ABBA :
# R J1 J2 R | J R R J …, jusqu'à bancs/STOP_J, au plus tard le 30/10 21:00 UTC (arrêt du pod à 22:00 UTC, minuterie5).
# Critère (Cowork, CW-412) : J ≥ R sur au moins 4 paires appariées ; sinon arrêt de l'intégration.
# Usage : HEAD_J=<sha ≥ correctif de D> R_DEBUT=<1er indice R libre> nohup bash ip.sh &
# Les drapeaux de J sont ceux de I (S2 + historique fidèle + inspect) ; le correctif de D est dans le code, pas dans un drapeau.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') ip : $*" | tee -a $W/runs/chaine_etapes.txt; }
S2="CHRYS_MOTEUR=1 CHRYS_MOTEUR_CLE=1 CHRYS_TUTO=0 CHRYS_MOTEUR_BUDGET_S=2 CHRYS_MOTEUR_BUDGET1_S=30 CHRYS_MOTEUR_CPU_JEU_S=60
 CHRYS_GARDE_MUR_S=600 CHRYS_GARDE_TOUR_S=90 CHRYS_MOTEUR_PROCESSUS=1 CHRYS_PARTIEL=2 CHRYS_AMODAL=1 CHRYS_FORMES=1
 CHRYS_COMPORTEMENT=1 CHRYS_BUT_SUPPOSE=1"  # = i_matin5.sh (I), à l'identique
# Le code du pod n'est pas un dépôt git : archive $W/j_head.tgz (git archive HEAD_J) + $W/j_head.txt, posées par A.
[ -n "$HEAD_J" ] && [ "$(cat $W/j_head.txt)" = "$HEAD_J" ] || { j "j_head.txt ≠ HEAD_J ($HEAD_J) : ARRÊT"; exit 1; }
if pgrep -f r_attente_run.sh >/dev/null; then touch $W/bancs/STOP_R; while [ ! -f $W/bancs/r_attente.FINI ]; do sleep 30; done; fi
tar xzf $W/j_head.tgz -C $R && j "code du pod mis à jour ($HEAD_J)"
grep -rq guessed_goal $R/chrysalide/arc3/ || { j "guessed_goal absent du code : ARRÊT"; exit 1; }
python3 $R/scripts/arc3/patcher_franzen.py $W/harnais > /dev/null && python3 $R/scripts/arc3/patcher_garde.py $W/harnais > /dev/null \
  && j "patcher_inspect : $(python3 $R/scripts/arc3/patcher_inspect.py $W/harnais 2>&1 | tail -1)" \
  || { j "patchs en échec : ARRÊT"; exit 1; }
# copie du harnais = dépôt (imports réécrits) et SANS import du paquet `chrysalide`, introuvable dans le harnais (J1 du 22/10)
python3 - $R/chrysalide/arc3/inspect_franzen.py $W/harnais/inference/chrysalide_arc3/inspect_franzen.py <<'PY2' \
  && j "inspect_franzen.py du harnais = dépôt, imports réécrits" || { j "inspect_franzen.py du harnais ≠ dépôt réécrit : ARRÊT"; exit 1; }
import sys
a = open(sys.argv[1]).read().replace("from chrysalide.arc3.", "from inference.chrysalide_arc3.").replace("from chrysalide.arc3 import", "from inference.chrysalide_arc3 import")
b = open(sys.argv[2]).read()
sys.exit(b != a or "from chrysalide." in b)
PY2
j "départ (HEAD $(git rev-parse --short HEAD), CW-412 jalon 1)"
k=${K_DEBUT:-1}; r=${R_DEBUT:?R_DEBUT}
while :; do
  for n in R$r J$k J$((k+1)) R$((r+1)) J$((k+2)) R$((r+2)) R$((r+3)) J$((k+3)); do
    [ -f $W/bancs/STOP_J ] && { j "STOP_J avant $n"; break 2; }
    [ "$(date -u +%s)" -ge "$(date -u -d '2026-10-30 21:00' +%s)" ] && { j "30/10 21:00 UTC"; break 2; }
    [ "$(df --output=avail -BG $W | tail -1 | tr -dc 0-9)" -ge 4 ] || { j "moins de 4 Go libres avant $n"; break 2; }
    a=(); case $n in J*) a=($S2 CHRYS_HISTORIQUE_FIDELE=1 CHRYS_INSPECT=1);; esac
    j "début $n"
    cd $R && bash scripts/pod/bloc.sh $n "${a[@]}" ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
    j "fin $n (code $?)"
    find $W/runs/$n -type f \( -name "*.jsonl" -o -name "*.log" \) -size +20k ! -name "*events*" -print0 | xargs -0 -r gzip -6
  done
  k=$((k+4)); r=$((r+4))
done
touch $W/bancs/ip.FINI; j "fini"
