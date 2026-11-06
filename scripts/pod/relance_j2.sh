#!/usr/bin/env bash
# SUR LE POD — RELANCE 2 (23/10 0 h, A) : la 1ʳᵉ relance (relance_j.sh) a échoué sur les fichiers « ._* » (AppleDouble) ajoutés par
# le tar de macOS (UnicodeDecodeError dans les patchs) ; archives refaites avec COPYFILE_DISABLE=1, fichiers ._ effacés du pod.
# J1 invalide déjà mis de côté. Bloc J (ef20366f + 971848f9), puis X (22f9751c + 971848f9, borne 2), puis R jusqu'au 30/10.
# Si ip.sh ou x.sh s'arrête sur un contrôle, la file passe directement aux passages R (jamais de GPU à vide).
W=/workspace
j() { echo "$(date '+%d/%m %H:%M') relance_j2 : $*" | tee -a $W/runs/chaine_etapes.txt; }
rm -f $W/bancs/ip.FINI $W/bancs/STOP_J $W/bancs/x.FINI
cp $W/head_ef20366f.tgz $W/j_head.tgz && cp $W/head_ef20366f.txt $W/j_head.txt
cp $W/head_22f9751c.tgz $W/x_head.tgz && cp $W/head_22f9751c.txt $W/x_head.txt
j "bloc J : R15 J1 J2 R16 | J3 R17 R18 J4"
(cd $W && HEAD_J="$(cat $W/j_head.txt)" R_DEBUT=15 K_DEBUT=1 bash $W/ip2_run.sh > $W/runs/ip2.log 2>&1 < /dev/null)
if [ -f $W/bancs/ip.FINI ]; then
  (cd $W && HEAD_X="$(cat $W/x_head.txt)" R_DEBUT=19 bash $W/x_run.sh > $W/runs/x.log 2>&1 < /dev/null)
  [ -f $W/bancs/x.FINI ] && j "X fini" || j "X arrêté sur un contrôle (x.log)"
else
  j "J arrêté sur un contrôle (ip2.log) : X non lancé"
fi
j "passages R jusqu'au 30/10"
rm -f $W/bancs/STOP_R $W/bancs/r_attente.FINI
cd $W && R_DEBUT=23 bash $W/r_attente_run.sh
