#!/usr/bin/env bash
# SUR LE POD (CW-361.2, CCM-071-D) : jeudi 22/10. STOP_M posé à 05:10 UTC → m0r_nuit s'arrête après sa partie en cours ;
# code du pod mis à jour (/workspace/i_head.tgz) ; patchs franzen, garde, puis inspect ; passage I = M0 + CHRYS_INSPECT=1 (le
# moteur calcule comme M0 mais ne joue jamais ; Franzen lit l'option par inspect_options()/inspect_model()). Puis reprise de
# test NEXTN 3 contre 2 étapes (CW-364, nextn.sh).
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
until [ "$(date -u +%Y%m%d%H%M)" -ge 202610220510 ]; do sleep 60; done
touch $W/bancs/STOP_M; j "i_matin : STOP_M posé (fin de la nuit M0 contre R après la partie en cours)"
while [ ! -f $W/bancs/m0r_nuit.FINI ]; do sleep 30; done
tar xzf $W/i_head.tgz -C $R && j "i_matin : code du pod mis à jour ($(cat $W/i_head.txt))"
grep -rq CHRYS_INSPECT $R/chrysalide/arc3/ || { j "i_matin : CHRYS_INSPECT absent du code : ARRÊT"; exit 1; }
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
# CW-364 : la modification du 22 (vitesse NEXTN 3 contre 2 étapes) remplace la reprise de M0 contre R
j "i_matin : départ du test NEXTN (CW-364)"; setsid nohup bash $W/nextn_run.sh > $W/runs/nextn.log 2>&1 < /dev/null &
