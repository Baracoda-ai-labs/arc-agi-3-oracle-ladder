#!/usr/bin/env bash
# SUR LE POD (CW-449, CW-436.2) : ABBA « bras de Franzen contre R » : un réglage du harnais de Franzen SEUL (moteur éteint, aucun
# CHRYS_MOTEUR), par ex. les consignes de D (CHRYS_REVUE=1 ; CHRYS_NIVEAUX_RESOLUS=1 contre son témoin =2). 4 paires :
# R C1 C2 R | C3 R R C4 (C = PREFIXE). Si TEMOIN_DRAPEAUX est donné, les « R » du bloc reçoivent ces drapeaux (bras contre témoin).
# Code : $W/<prefixe>_head.tgz (git archive SHA) + <prefixe>_head.txt ; patchs franzen, garde, inspect ET conseils.
# Usage : PREFIXE=Q HEAD_C=<sha> DRAPEAUX="CHRYS_REVUE=1" [TEMOIN_DRAPEAUX="…"] R_DEBUT=<n> ATTENDRE=<fichier de bancs/> setsid nohup bash abba_franzen.sh &
W=/workspace; R=$W/chrysalide3
P=${PREFIXE:?PREFIXE}; ATT=${ATTENDRE:-x.FINI}
j() { echo "$(date '+%d/%m %H:%M') abba_$P : $*" | tee -a $W/runs/chaine_etapes.txt; }
S2="CHRYS_MOTEUR=1 CHRYS_MOTEUR_CLE=1 CHRYS_TUTO=0 CHRYS_MOTEUR_BUDGET_S=2 CHRYS_MOTEUR_BUDGET1_S=30 CHRYS_MOTEUR_CPU_JEU_S=60
 CHRYS_GARDE_MUR_S=600 CHRYS_GARDE_TOUR_S=90 CHRYS_MOTEUR_PROCESSUS=1 CHRYS_PARTIEL=2 CHRYS_AMODAL=1 CHRYS_FORMES=1
 CHRYS_COMPORTEMENT=1 CHRYS_BUT_SUPPOSE=1"  # = i_matin5.sh / ip.sh
[ -n "$HEAD_C" ] && [ "$(cat $W/${P}_head.txt)" = "$HEAD_C" ] || { j "${P}_head.txt ≠ HEAD_C ($HEAD_C) : ARRÊT"; exit 1; }
while [ ! -f $W/bancs/$ATT ]; do sleep 30; done
# CW-424 : si des passages R d'attente tournent (apres_j.sh), les arrêter entre deux passages
if pgrep -f r_attente_run.sh >/dev/null; then touch $W/bancs/STOP_R; while [ ! -f $W/bancs/r_attente.FINI ]; do sleep 30; done; fi
tar xzf $W/${P}_head.tgz -C $R && j "code du pod mis à jour ($HEAD_C)"
[ -f $R/chrysalide/arc3/conseils.py ] && [ -f $R/scripts/arc3/patcher_conseils.py ] || { j "conseils absents du code : ARRÊT"; exit 1; }
python3 $R/scripts/arc3/patcher_franzen.py $W/harnais > /dev/null && python3 $R/scripts/arc3/patcher_garde.py $W/harnais > /dev/null \
  && python3 $R/scripts/arc3/patcher_inspect.py $W/harnais > /dev/null \
  && j "patcher_conseils : $(python3 $R/scripts/arc3/patcher_conseils.py $W/harnais 2>&1 | tail -1)" || { j "patchs en échec : ARRÊT"; exit 1; }
# copie du harnais = dépôt, telle quelle ou imports réécrits comme patcher_franzen.py (« chrysalide.arc3 » → « inference.chrysalide_arc3 »)
for f in garde.py moteur.py inspect_franzen.py conseils.py; do
  [ -f $W/harnais/inference/chrysalide_arc3/$f ] || continue
  python3 - $R/chrysalide/arc3/$f $W/harnais/inference/chrysalide_arc3/$f <<'PY2' && j "$f du harnais = dépôt" || { j "$f du harnais ≠ dépôt : ARRÊT"; exit 1; }
import sys
a = open(sys.argv[1]).read().replace("from chrysalide.arc3.", "from inference.chrysalide_arc3.").replace("from chrysalide.arc3 import", "from inference.chrysalide_arc3 import")
b = open(sys.argv[2]).read()
sys.exit(b not in (a, open(sys.argv[1]).read()))  # inspect_franzen.py est copié tel quel par patcher_inspect
PY2
done
j "départ ($HEAD_C, drapeaux : $DRAPEAUX)"
r=${R_DEBUT:?R_DEBUT}
for n in R$r ${P}1 ${P}2 R$((r+1)) ${P}3 R$((r+2)) R$((r+3)) ${P}4; do
  [ -f $W/bancs/STOP_$P ] && { j "STOP_$P avant $n"; break; }
  [ "$(df --output=avail -BG $W | tail -1 | tr -dc 0-9)" -ge 4 ] || { j "moins de 4 Go libres avant $n"; break; }
  a=(); case $n in R*) a=(${TEMOIN_DRAPEAUX:-});; *) a=($DRAPEAUX);; esac   # moteur éteint : seuls les drapeaux du bras
  j "début $n"
  cd $R && bash scripts/pod/bloc.sh $n "${a[@]}" ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
  j "fin $n (code $?)"
  find $W/runs/$n -type f \( -name "*.jsonl" -o -name "*.log" \) -size +20k ! -name "*events*" -print0 | xargs -0 -r gzip -6
done
touch $W/bancs/abba_$P.FINI; j "fini"
