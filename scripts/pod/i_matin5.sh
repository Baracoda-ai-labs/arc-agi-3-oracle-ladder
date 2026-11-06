#!/usr/bin/env bash
# SUR LE POD (CW-368) : jeudi 22/10. STOP_N posé à 04:50 UTC → NEXTN s'arrête après son passage en cours (serveur remis à 3 étapes) ;
# code à jour + patchs franzen, garde, inspect ; passage I1 = M0 + CHRYS_INSPECT=1 (≈ 7 h 45 Paris) ; puis 3ᵉ bloc R contre W
# (R5 W5 W6 R6, CW-372 ; W = surcharges env_W5/W6.sh) ; puis I contre R en ABBA (CCM-346-A ; NEXTN tranché).
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
for n in R5 W5 W6 R6; do  # CW-372 : 3ᵉ bloc R contre W (notes de Franzen rouvertes)
  [ -f $W/bancs/STOP_W ] && { j "i_matin : STOP_W avant $n"; break; }
  [ "$(df --output=avail -BG $W | tail -1 | tr -dc 0-9)" -ge 4 ] || { j "i_matin : moins de 4 Go libres avant $n"; break; }
  j "i_matin : début $n (surcharge : $(ls $R/scripts/pod/env_$n.sh 2>/dev/null || echo aucune))"
  cd $R && bash scripts/pod/bloc.sh $n ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
  j "i_matin : fin $n (code $?)"
  find $W/runs/$n -type f \( -name "*.jsonl" -o -name "*.log" \) -size +20k ! -name "*events*" -print0 | xargs -0 -r gzip -6
done
# CCM-346-A : NEXTN est tranché (B rejeté, CCM-345-A) ; après le bloc R/W, le GPU sert à I contre R (voie 2, comparaison voulue
# par D : I a le coût de calcul de M0) : I2 R7 R8 I3 | R9 I4 I5 R10 …, jusqu'à bancs/STOP_I. Requêtes de I non compressées.
rm -f $W/bancs/STOP_N
k=2; r=7
while :; do
  for n in I$k R$r R$((r+1)) I$((k+1)) R$((r+2)) I$((k+2)) I$((k+3)) R$((r+3)); do
    [ -f $W/bancs/STOP_I ] && { j "i_matin : STOP_I avant $n"; break 2; }
    [ "$(date -u +%s)" -ge "$(date -u -d '2026-10-24 04:50' +%s)" ] && break 2
    [ "$(df --output=avail -BG $W | tail -1 | tr -dc 0-9)" -ge 4 ] || { j "i_matin : moins de 4 Go libres avant $n"; break 2; }
    a=(); case $n in I*) a=($S2 CHRYS_HISTORIQUE_FIDELE=1 CHRYS_INSPECT=1);; esac
    j "i_matin : début $n"
    cd $R && bash scripts/pod/bloc.sh $n "${a[@]}" ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
    j "i_matin : fin $n (code $?)"
    find $W/runs/$n -type f \( -name "*.jsonl" -o -name "*.log" \) -size +20k ! -name "*events*" ! -name "*requests*" -print0 | xargs -0 -r gzip -6
  done
  k=$((k+4)); r=$((r+4))
done
touch $W/bancs/i_matin.FINI; j "i_matin fini"
