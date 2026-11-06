#!/usr/bin/env bash
# SUR LE POD (A, CCM-324-A) : file GPU après R contre W (21/10).
#  0. attend la fin de R contre W (bancs/w_abba2.FINI) ; met à jour le code (/workspace/suite_head.tgz) et re-patche le harnais ;
#  1. ft09 + re86, 4 variantes de D EN PARALLÈLE (un harnais par variante, CCM-058-D) : R, H1, H1f, P ; 2 tirages ;
#  2. 2 × 2 de la fusion, bras moteur (CW-350, CCM-061-D) : M0 = S2 + HISTORIQUE_FIDELE ; M1 = M0 + notes (slim, gardées) ;
#     ABBA × 2 (M0a M1a M1b M0b | M0c M1c M1d M0d) ; F0/F1 = R/W déjà mesurés ;
#  3. V (après victoire + économie, CW-332) contre P, ABBA × 2.
# CW-352 : tirage 1 avant la fenêtre de la sonde Qwen (14:35-15:05 UTC), tirage 2 après.
# Arrêt : bancs/STOP_S, disque < 4 Go, ou 24/10 04:50 UTC. Chaque passage compressé à sa fin.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
anon() { awk '/^anon /{print int($2/2^30)}' /sys/fs/cgroup/memory.stat; }
ok() {
  [ -f $W/bancs/STOP_S ] && { j "suite : STOP_S"; return 1; }
  [ "$(date -u +%s)" -ge "$(date -u -d '2026-10-24 04:50' +%s)" ] && { j "suite : 24/10 04:50 UTC"; return 1; }
  [ "$(df --output=avail -BG $W | tail -1 | tr -dc 0-9)" -ge 4 ] || { j "suite : moins de 4 Go libres"; return 1; }
  return 0
}
compresser() { find $W/runs/$1 -type f \( -name "*.jsonl" -o -name "*.log" \) -size +20k ! -name "*events*" -print0 | xargs -0 -r gzip -6; }
passe() {  # passe <nom> [jeux|-] [VAR=val …]
  local n=$1 jeux=$2; shift 2
  j "suite : début $n anon $(anon) Go"
  if [ "$jeux" = "-" ]; then
    (cd $R && bash scripts/pod/bloc.sh $n "$@" ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null)
  else
    (cd $R && bash scripts/pod/bloc.sh $n "$@" ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 -- "$jeux" > $W/runs/$n.log 2>&1 < /dev/null)
  fi
  j "suite : fin $n (code $?)"; compresser $n
}
while [ ! -f $W/bancs/w_abba2.FINI ]; do sleep 30; done
tar xzf $W/suite_head.tgz -C $R && j "suite : code du pod mis à jour ($(cat $W/suite_head.txt))"
for f in CHRYS_HISTORIQUE_FIDELE CHRYS_APRES_VICTOIRE CHRYS_CALCULE_SANS_JOUER; do
  grep -rq $f $R/chrysalide/arc3/ || { j "suite : $f absent du code : ARRÊT"; exit 1; }
done
python3 $R/scripts/arc3/patcher_franzen.py $W/harnais > /dev/null && python3 $R/scripts/arc3/patcher_garde.py $W/harnais \
  || { j "suite : patchs en échec : ARRÊT"; exit 1; }
S2="CHRYS_MOTEUR=1 CHRYS_MOTEUR_CLE=1 CHRYS_TUTO=0 CHRYS_MOTEUR_BUDGET_S=2 CHRYS_MOTEUR_BUDGET1_S=30 CHRYS_MOTEUR_CPU_JEU_S=60
 CHRYS_GARDE_MUR_S=600 CHRYS_GARDE_TOUR_S=90 CHRYS_MOTEUR_PROCESSUS=1 CHRYS_PARTIEL=2 CHRYS_AMODAL=1 CHRYS_FORMES=1
 CHRYS_COMPORTEMENT=1 CHRYS_BUT_SUPPOSE=1"
NOTES="ARC3_MEMORY_SECTIONS=slim ARC3_WM_WIPE_ON_LEVEL=0"
JEUX='["ft09","re86"]'
# 1. quatre variantes en parallèle, deux tirages
for t in 1 2; do
  ok || exit 0
  # CW-352 : fenêtre GPU de la 2ᵉ sonde Qwen (H), 14:35-15:05 UTC : aucun passage ne démarre dedans ni ne la chevauche
  if [ $t = 2 ]; then until [ "$(date -u +%H%M)" -ge 1505 ]; do sleep 30; done; j "suite : fin de la fenêtre de la sonde, reprise"; fi
  j "suite : ft09/re86, tirage $t, 4 variantes en parallèle"
  passe FT_R$t "$JEUX" &
  passe FT_H1$t "$JEUX" $S2 &
  passe FT_H1f$t "$JEUX" $S2 CHRYS_HISTORIQUE_FIDELE=1 &
  passe FT_P$t "$JEUX" $S2 CHRYS_STAGNATION_COUPS=100000000 &
  wait
done
# 2. 2 × 2, bras moteur ; 3. V contre P
for n in M0a M1a M1b M0b M0c M1c M1d M0d Pa Va Vb Pb Pc Vc Vd Pd; do
  ok || break
  case $n in
    M0*) passe $n - $S2 CHRYS_HISTORIQUE_FIDELE=1 ;;
    M1*) passe $n - $S2 CHRYS_HISTORIQUE_FIDELE=1 $NOTES ;;
    V*)  passe $n - $S2 CHRYS_APRES_VICTOIRE=1 CHRYS_ECONOMIE=1 ;;
    P*)  passe $n - $S2 CHRYS_STAGNATION_COUPS=100000000 ;;
  esac
done
touch $W/bancs/suite_21-10.FINI; j "suite 21/10 finie"
