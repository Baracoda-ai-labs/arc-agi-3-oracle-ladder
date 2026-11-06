#!/usr/bin/env bash
# SUR LE POD (CW-444) : ABBA générique « candidat moteur contre R », sur le modèle de x.sh (relève X), prêt à recevoir chaque
# candidat positif en moteur seul. 4 paires : R C1 C2 R | C3 R R C4, où C = PREFIXE (une lettre libre : Y, Z…).
# Code : archive $W/<prefixe>_head.tgz (git archive SHA, faite avec COPYFILE_DISABLE=1) + <prefixe>_head.txt.
# Drapeaux du candidat : S2 (= I/J/X) + HISTORIQUE_FIDELE + RELEVE + BORNE 2 (comme X) + DRAPEAUX (ceux du candidat, ex. CHRYS_FILMS_P1=1).
# Part quand bancs/<ATTENDRE> existe (défaut x.FINI) ; arrête d'abord les passages R d'attente.
# Usage : PREFIXE=Y HEAD_C=<sha> DRAPEAUX="CHRYS_X=1 CHRYS_Y=1" R_DEBUT=<1er R libre> ATTENDRE=x.FINI setsid nohup bash abba_candidat.sh &
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
j "départ ($HEAD_C, drapeaux : $DRAPEAUX)"
r=${R_DEBUT:?R_DEBUT}
for n in R$r ${P}1 ${P}2 R$((r+1)) ${P}3 R$((r+2)) R$((r+3)) ${P}4; do
  [ -f $W/bancs/STOP_$P ] && { j "STOP_$P avant $n"; break; }
  [ "$(df --output=avail -BG $W | tail -1 | tr -dc 0-9)" -ge 4 ] || { j "moins de 4 Go libres avant $n"; break; }
  a=(); case $n in R*) ;; *) a=($S2 CHRYS_HISTORIQUE_FIDELE=1 CHRYS_RELEVE=1 CHRYS_RELEVE_BORNE=2 $DRAPEAUX);; esac
  j "début $n"
  cd $R && bash scripts/pod/bloc.sh $n "${a[@]}" ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
  j "fin $n (code $?)"
  find $W/runs/$n -type f \( -name "*.jsonl" -o -name "*.log" \) -size +20k ! -name "*events*" -print0 | xargs -0 -r gzip -6
done
touch $W/bancs/abba_$P.FINI; j "fini"
