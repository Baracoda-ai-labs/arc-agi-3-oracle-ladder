#!/usr/bin/env bash
# SPDX-License-Identifier: MIT-0
# SUR LE POD, appelé par bloc.sh à la fin de H : blocs T2.14 (CW-094/095/098/099/101), SEULEMENT si experiments/T2.14/GO existe.
# Ordre (le serveur ne redémarre qu'une fois) : doses D30/D60 × 3 graines (serveur à 10 requêtes, comme V2p), puis F14 × 3
# graines (serveur relancé à 14 requêtes). Chaque bloc écrit son coût et sa décision dans /workspace/runs/DEPENSES.tsv.
# Décisions (CW-101) — doses : si la pente « tours/jeu → RHAE officiel » est ≥ +5 points par doublement (3 graines, IC > 0),
#   le débit devient prioritaire pour la soumission (F14, ordonnanceur) ; sinon non. F14 : si F14 ≥ R0 + 3 points officiels
#   (3 graines, contre R0 + FC2 + Kaggle v3), le notebook de soumission passe à 14 flux ; sinon il reste à 10.
cd "$(dirname "$0")/../.."
W=/workspace
journal() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
cout() { echo -e "$(date '+%d/%m %H:%M')\t$1\t$2\t$3" >> $W/runs/DEPENSES.tsv; }   # bloc, heures, décision éclairée
[ -f experiments/T2.14/GO ] || { journal "T2.14 sauté : pas de feu vert (experiments/T2.14/GO absent)"; exit 0; }
CRIB='["bp35","lf52","ka59","ls20","re86","sp80","dc22","sc25","tr87","m0r0"]'
bloc() {  # nom, décision, puis arguments de bloc.sh
  local nom=$1 dec=$2; shift 2
  [ -f "$W/runs/$nom/FINI" ] && { journal "$nom déjà fait"; return; }
  local t0; t0=$(date +%s); journal "début $nom"
  bash scripts/pod/bloc.sh "$nom" "$@"; journal "fin $nom (code $?)"
  cout "$nom" "$(python3 -c "print(round(($(date +%s) - $t0) / 3600, 2))")" "$dec"
}
# Créneau Flash-Next pour le lot LLM de B (CCM-081-B, test de format) : entre H et les doses, serveur à 10 requêtes déjà
# levé, aucun bloc en cours. Seulement si /workspace/bancs/creneau_llm.sh existe ; 50 min au plus (≈ 1,8 €).
if [ -f $W/bancs/creneau_llm.sh ] && [ ! -f $W/bancs/creneau_llm.FINI ]; then
  t0=$(date +%s); journal "début créneau LLM (B, test de format)"
  timeout 3000 bash $W/bancs/creneau_llm.sh > $W/bancs/creneau_llm.log 2>&1; echo "code $?" > $W/bancs/creneau_llm.FINI
  journal "fin créneau LLM ($(cat $W/bancs/creneau_llm.FINI))"
  cout "creneau_llm" "$(python3 -c "print(round(($(date +%s) - $t0) / 3600, 2))")" "format : 1 requête contrainte ou 2 passes ?"
fi
for g in 1 2 3; do
  s=""; [ $g -gt 1 ] && s="_g$g"
  for d in 30 60; do
    bloc "D$d$s" "dose-réponse (pente tours → RHAE)" MAX_RUNTIME_MINUTES=$d -- "$CRIB"
  done
done
# 2ᵉ chance du créneau LLM (CCM-085-B) : si le script est arrivé après H, il passe ici, entre les doses et FC2b.
if [ -f $W/bancs/creneau_llm.sh ] && [ ! -f $W/bancs/creneau_llm.FINI ]; then
  t0=$(date +%s); journal "début créneau LLM (B, test de format, 2ᵉ chance)"
  timeout 3000 bash $W/bancs/creneau_llm.sh > $W/bancs/creneau_llm.log 2>&1; echo "code $?" > $W/bancs/creneau_llm.FINI
  journal "fin créneau LLM ($(cat $W/bancs/creneau_llm.FINI))"
  cout "creneau_llm" "$(python3 -c "print(round(($(date +%s) - $t0) / 3600, 2))")" "format : 1 requête contrainte ou 2 passes ?"
fi
# FC2 du 17/10 invalide : le serveur a été tué (OOM du conteneur) par la recherche de traces de A à 21 h 20 UTC ; on le
# refait ici, à 10 requêtes, avant le passage à 14 flux (même configuration que R0).
bloc "FC2b" "A/A 25 jeux : bruit d'un run à l'autre (reprise de FC2)"
# 3ᵉ chance du créneau LLM : la 2ᵉ a échoué en 10 s (docs/ non synchronisé sur le pod, faute de A) ; serveur encore à 10.
if [ -f $W/bancs/creneau_llm.sh ] && [ ! -f $W/bancs/creneau_llm.FINI ]; then
  t0=$(date +%s); journal "début créneau LLM (B, test de format, 3ᵉ chance)"
  timeout 3000 bash $W/bancs/creneau_llm.sh > $W/bancs/creneau_llm.log 2>&1; echo "code $?" > $W/bancs/creneau_llm.FINI
  journal "fin créneau LLM ($(cat $W/bancs/creneau_llm.FINI))"
  cout "creneau_llm" "$(python3 -c "print(round(($(date +%s) - $t0) / 3600, 2))")" "format : 1 requête contrainte ou 2 passes ?"
fi
if grep -q "flux14" experiments/T2.14/GO; then
  journal "redémarrage du serveur à 14 requêtes"
  for p in $(pgrep -f "sglang serve"); do kill "$p"; done; sleep 20
  export SGL_MAXREQ=14   # lu par franzen_lanceur.py quand bloc.sh relance le serveur
  for g in 1 2 3; do
    s=""; [ $g -gt 1 ] && s="_g$g"
    bloc "F14$s" "14 flux pour la soumission ?" ARC3_MAX_ACTIVE_STREAMS=14
  done
fi
