#!/usr/bin/env bash
# SUR LE POD (CW-420, CCM-078-D) : relève conditionnelle X (CHRYS_RELEVE=1 : le moteur prend la main au niveau qui suit une victoire
# de Franzen si sa porte de confiance l'accepte ; refus côté moteur de C ; HISTORIQUE_FIDELE rend la main avec l'historique) contre R,
# 4 paires : R X1 X2 R | X3 R R X4. Part après ip.sh (bancs/ip.FINI). Code : archive $W/x_head.tgz (git archive HEAD_X) + x_head.txt.
# Critère (CW-412.2) : X − R ≥ +1 point apparié.
# Usage : HEAD_X=c7ee12b4 R_DEBUT=<1er indice R libre> setsid nohup bash x.sh &
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') x : $*" | tee -a $W/runs/chaine_etapes.txt; }
S2="CHRYS_MOTEUR=1 CHRYS_MOTEUR_CLE=1 CHRYS_TUTO=0 CHRYS_MOTEUR_BUDGET_S=2 CHRYS_MOTEUR_BUDGET1_S=30 CHRYS_MOTEUR_CPU_JEU_S=60
 CHRYS_GARDE_MUR_S=600 CHRYS_GARDE_TOUR_S=90 CHRYS_MOTEUR_PROCESSUS=1 CHRYS_PARTIEL=2 CHRYS_AMODAL=1 CHRYS_FORMES=1
 CHRYS_COMPORTEMENT=1 CHRYS_BUT_SUPPOSE=1"  # = i_matin5.sh / ip.sh
[ -n "$HEAD_X" ] && [ "$(cat $W/x_head.txt)" = "$HEAD_X" ] || { j "x_head.txt ≠ HEAD_X ($HEAD_X) : ARRÊT"; exit 1; }
while [ ! -f $W/bancs/ip.FINI ]; do sleep 30; done
# CW-424 : si des passages R d'attente tournent (apres_j.sh), les arrêter entre deux passages
if pgrep -f r_attente_run.sh >/dev/null; then touch $W/bancs/STOP_R; while [ ! -f $W/bancs/r_attente.FINI ]; do sleep 30; done; fi
tar xzf $W/x_head.tgz -C $R && j "code du pod mis à jour ($HEAD_X)"
grep -q CHRYS_RELEVE $R/chrysalide/arc3/moteur.py && grep -q CHRYS_RELEVE $R/chrysalide/arc3/garde.py || { j "CHRYS_RELEVE absent : ARRÊT"; exit 1; }
python3 $R/scripts/arc3/patcher_franzen.py $W/harnais > /dev/null && python3 $R/scripts/arc3/patcher_garde.py $W/harnais > /dev/null \
  && j "patcher_inspect : $(python3 $R/scripts/arc3/patcher_inspect.py $W/harnais 2>&1 | tail -1)" || { j "patchs en échec : ARRÊT"; exit 1; }
# copie du harnais = dépôt, telle quelle ou imports réécrits comme patcher_franzen.py (« chrysalide.arc3 » → « inference.chrysalide_arc3 »)
for f in garde.py moteur.py inspect_franzen.py; do
  [ -f $W/harnais/inference/chrysalide_arc3/$f ] || continue
  python3 - $R/chrysalide/arc3/$f $W/harnais/inference/chrysalide_arc3/$f <<'PY2' && j "$f du harnais = dépôt" || { j "$f du harnais ≠ dépôt : ARRÊT"; exit 1; }
import sys
a = open(sys.argv[1]).read().replace("from chrysalide.arc3.", "from inference.chrysalide_arc3.").replace("from chrysalide.arc3 import", "from inference.chrysalide_arc3 import")
b = open(sys.argv[2]).read()
sys.exit(b not in (a, open(sys.argv[1]).read()))  # inspect_franzen.py est copié tel quel par patcher_inspect
PY2
done
j "départ ($HEAD_X, CW-420)"
r=${R_DEBUT:?R_DEBUT}
for n in R$r X1 X2 R$((r+1)) X3 R$((r+2)) R$((r+3)) X4; do
  [ -f $W/bancs/STOP_X ] && { j "STOP_X avant $n"; break; }
  [ "$(df --output=avail -BG $W | tail -1 | tr -dc 0-9)" -ge 4 ] || { j "moins de 4 Go libres avant $n"; break; }
  a=(); case $n in X*) a=($S2 CHRYS_HISTORIQUE_FIDELE=1 CHRYS_RELEVE=1 CHRYS_RELEVE_BORNE=2);; esac  # borne 2 : CW-425
  j "début $n"
  cd $R && bash scripts/pod/bloc.sh $n "${a[@]}" ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
  j "fin $n (code $?)"
  find $W/runs/$n -type f \( -name "*.jsonl" -o -name "*.log" \) -size +20k ! -name "*events*" -print0 | xargs -0 -r gzip -6
done
touch $W/bancs/x.FINI; j "fini"
