#!/usr/bin/env bash
# SUR LE POD (CW-308/309, brouillon de Cowork relu et corrigé par A) : premier essai complet de l'HYBRIDE Franzen + moteur,
# nuit du 20 au 21/10. Référence appariée : R0e → R0h (Franzen pur, même serveur).
#   HC = harnais PATCHÉ, tous les CHRYS_* éteints (moteur débranché) : doit reproduire Franzen au bruit près (contrôle F-C2) ;
#   H0 = S2 + prise de main sur stagnation (CHRYS_STAGNATION_COUPS=200) ; H1 = S2 seul (prise de main dès qu'un plan existe) ;
#   R0i… = Franzen pur intercalé (dérive du serveur). 20 jeux NON témoins (défaut de bloc.sh), 10 flux, 48 min.
# Corrections de A : (1) code du pod mis à jour APRÈS R0h depuis l'archive de HEAD déposée (/workspace/h0_head.tgz) ;
# (2) contrôle HC en premier ; (3) garde mémoire avant chaque passage (> 150 Go : arrêt des bras but/sous_buts du ×100,
# jamais du serveur) ; (4) heure en UTC explicite ; (5) 20 jeux, pas 25 (les 5 témoins ne sont jamais joués hors jalon).
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
anon() { awk '/^anon /{print int($2/2^30)}' /sys/fs/cgroup/memory.stat; }
while [ ! -f $W/bancs/r0gh.FINI ]; do sleep 60; done
[ "$(df --output=avail -BG $W | tail -1 | tr -dc 0-9)" -ge 6 ] || { j "h0 : moins de 6 Go libres sur /workspace : ARRÊT"; exit 1; }
tar xzf $W/h0_head.tgz -C $R && j "h0 : code du pod mis à jour ($(cat $W/h0_head.txt))"
grep -q CHRYS_STAGNATION_COUPS $R/chrysalide/arc3/garde.py || { j "h0 : garde.py sans STAGNATION, copie pas à jour : ARRÊT"; exit 1; }
python3 $R/scripts/arc3/patcher_franzen.py $W/harnais > /dev/null && python3 $R/scripts/arc3/patcher_garde.py $W/harnais \
  || { j "h0 : patchs du harnais en échec : ARRÊT"; exit 1; }
S2="CHRYS_MOTEUR=1 CHRYS_MOTEUR_CLE=1 CHRYS_TUTO=0 CHRYS_MOTEUR_BUDGET_S=2 CHRYS_MOTEUR_BUDGET1_S=30 CHRYS_MOTEUR_CPU_JEU_S=60
 CHRYS_GARDE_MUR_S=600 CHRYS_GARDE_TOUR_S=90 CHRYS_MOTEUR_PROCESSUS=1 CHRYS_PARTIEL=2 CHRYS_AMODAL=1 CHRYS_FORMES=1
 CHRYS_COMPORTEMENT=1 CHRYS_BUT_SUPPOSE=1"   # = variante S2 de scripts/arc3/faire_notebook_S.py
# CW-313 (Thomas, 20 h 15) : un seul hybride (H1) contre un contrôle passif à même code (P) ; H0 abandonné
for n in HC P1 H1a H1b P2 H1c P3 P4 H1d P5 H1e; do
  h=$(date -u +%H%M); [ "$h" -ge 0450 ] && [ "$h" -lt 1200 ] && { j "h0 : 04:50 UTC, plus le temps d'un passage avant l'arrêt de 06:00 UTC : arrêt avant $n"; break; }
  if [ "$(anon)" -gt 150 ]; then
    j "h0 : mémoire $(anon) Go > 150 avant $n : arrêt des bras but/sous_buts du ×100"
    for p in $(pgrep -f 'budget100.py .* (but|sous_buts) '); do kill "$p"; done; sleep 30
  fi
  # P = S2, moteur allumé mais jamais de prise de main (seuil jamais atteint). garde.tour() sort AVANT b.tour() : le moteur
  # observe les coups mais ne calcule ni induction ni plan → charge CPU « non contrôlée » (A, CCM-289-A)
  a=(); case $n in H0*) a=($S2 CHRYS_STAGNATION_COUPS=200);; H1*) a=($S2);; P*) a=($S2 CHRYS_STAGNATION_COUPS=100000000);; esac
  j "h0 : début $n anon $(anon) Go"
  cd $R && bash scripts/pod/bloc.sh $n "${a[@]}" ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
  j "h0 : fin $n (code $?)"
  # disque /workspace plein le 20/10 à 20 h 19 (R0h perdu) : chaque passage fini est compressé (gzip, sans perte)
  find $W/runs/$n -type f \( -name "*.jsonl" -o -name "*.log" \) -size +20k -print0 | xargs -0 -r gzip -6
  j "h0 : $n compressé ; disque libre $(df -h $W | awk 'NR==2{print $4}')"
done
touch $W/bancs/h0.FINI; j "h0 fini"
