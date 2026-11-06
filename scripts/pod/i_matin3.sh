#!/usr/bin/env bash
# SUR LE POD (CW-368) : jeudi 22/10. STOP_N posé à 04:50 UTC → NEXTN s'arrête après son passage en cours (serveur remis à 3 étapes) ;
# code à jour + patchs franzen, garde, inspect ; passage I1 = M0 + CHRYS_INSPECT=1 (≈ 7 h 45 Paris) ; puis reprise de NEXTN au bloc
# suivant (CW-364, journée du 22).
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
until [ "$(date -u +%Y%m%d%H%M)" -ge 202610220450 ]; do sleep 60; done
touch $W/bancs/STOP_N; j "i_matin : STOP_N posé (NEXTN s'arrête après son passage en cours)"
while [ ! -f $W/bancs/nextn.FINI ]; do sleep 30; done
tar xzf $W/i_head.tgz -C $R && j "i_matin : code du pod mis à jour ($(cat $W/i_head.txt))"
grep -rq CHRYS_INSPECT $R/chrysalide/arc3/ || { j "i_matin : CHRYS_INSPECT absent : ARRÊT"; exit 1; }
python3 $R/scripts/arc3/patcher_franzen.py $W/harnais > /dev/null && python3 $R/scripts/arc3/patcher_garde.py $W/harnais > /dev/null \
  && j "i_matin : patcher_inspect : $(python3 $R/scripts/arc3/patcher_inspect.py $W/harnais 2>&1 | tail -1)" \
  || { j "i_matin : patchs en échec : ARRÊT"; exit 1; }
S2="CHRYS_MOTEUR=1 CHRYS_MOTEUR_CLE=1 CHRYS_TUTO=0 CHRYS_MOTEUR_BUDGET_S=2 CHRYS_MOTEUR_BUDGET1_S=30 CHRYS_MOTEUR_CPU_JEU_S=60
 CHRYS_GARDE_MUR_S=600 CHRYS_GARDE_TOUR_S=90 CHRYS_MOTEUR_PROCESSUS=1 CHRYS_PARTIEL=2 CHRYS_AMODAL=1 CHRYS_FORMES=1
 CHRYS_COMPORTEMENT=1 CHRYS_BUT_SUPPOSE=1"
j "i_matin : début I1"
cd $R && bash scripts/pod/bloc.sh I1 $S2 CHRYS_HISTORIQUE_FIDELE=1 CHRYS_INSPECT=1 ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/I1.log 2>&1 < /dev/null
j "i_matin : fin I1 (code $?)"
find $W/runs/I1 -type f \( -name "*.jsonl" -o -name "*.log" \) -size +20k ! -name "*events*" ! -name "*requests*" -print0 | xargs -0 -r gzip -6
m=$(ls -d $W/runs/[AB][0-9]* 2>/dev/null | sed 's#.*/[AB]##' | grep -E '^[0-9]+$' | sort -n | tail -1); m=${m:-0}
debut=$(( (m + 3) / 4 * 4 + 1 ))
rm -f $W/bancs/STOP_N $W/bancs/nextn.FINI
j "i_matin : reprise de NEXTN au bloc $debut"; NEXTN_DEBUT=$debut setsid nohup bash $W/nextn_run.sh > $W/runs/nextn2.log 2>&1 < /dev/null &
