#!/usr/bin/env bash
# SUR LE POD : cale /usr/local/bin/runpodctl (CW-099, Thomas : « pas besoin d'arrêter le pod »). La chaîne de nuit déjà lancée
# a un trap d'arrêt qu'on ne peut plus modifier ; cette cale bloque « stop pod » SAUF s'il vient du garde-fou d'inactivité de
# Cowork (pod vraiment à vide) ou si /workspace/AUTORISE_ARRET existe. Tout le reste passe au vrai runpodctl.
if [ "$1" = "stop" ] && [ ! -f /workspace/AUTORISE_ARRET ] && ! ps -o args= -p "$PPID" | grep -q veille_inactivite; then
  echo "$(date '+%d/%m %H:%M') arrêt du pod REFUSÉ par la cale (CW-099) ; appelant : $(ps -o args= -p "$PPID" | cut -c1-80)" >> /workspace/runs/arrets_refuses.log
  exit 0
fi
exec /usr/bin/runpodctl "$@"
