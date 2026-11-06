#!/usr/bin/env bash
# SUR LE POD (22/10 23 h 30, A, CCM-365-A) : J1 invalide (ModuleNotFoundError 'chrysalide' dans la copie de inspect_franzen.py →
# repli Franzen dès qu'une option existait). STOP_J posé pendant J1 ; à la fin de J1 : J1 mis de côté, bloc J relancé en entier
# sur ef20366f + patcher_inspect corrigé (971848f9), puis X sur 22f9751c + même correctif (borne 2), puis passages R jusqu'au 30/10.
W=/workspace
j() { echo "$(date '+%d/%m %H:%M') relance_j : $*" | tee -a $W/runs/chaine_etapes.txt; }
while [ ! -f $W/bancs/ip.FINI ]; do sleep 30; done
mv $W/runs/J1 $W/runs/J1_invalide_import && mv $W/runs/J1.log $W/runs/J1_invalide_import.log
rm -f $W/bancs/ip.FINI $W/bancs/STOP_J
cp $W/head_ef20366f.tgz $W/j_head.tgz && cp $W/head_ef20366f.txt $W/j_head.txt
cp $W/head_22f9751c.tgz $W/x_head.tgz && cp $W/head_22f9751c.txt $W/x_head.txt
j "J1 mis de côté (J1_invalide_import) ; bloc J relancé : R15 J1 J2 R16 | J3 R17 R18 J4"
(cd $W && HEAD_J="$(cat $W/j_head.txt)" R_DEBUT=15 K_DEBUT=1 bash $W/ip2_run.sh > $W/runs/ip2.log 2>&1 < /dev/null) &
sleep 120
(cd $W && HEAD_X="$(cat $W/x_head.txt)" R_DEBUT=19 bash $W/x_run.sh > $W/runs/x.log 2>&1 < /dev/null)
j "X terminé ou arrêté (voir x.log) ; passages R jusqu'au 30/10"
rm -f $W/bancs/STOP_R $W/bancs/r_attente.FINI
cd $W && R_DEBUT=23 bash $W/r_attente_run.sh
