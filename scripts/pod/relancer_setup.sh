#!/usr/bin/env bash
# SUR LE POD : arrête une installation en cours (constructeur Pennyroyal compris) et la relance, détachée.
# Passer par ce fichier évite qu'un pkill -f lancé à distance ne tue sa propre session.
moi=$$
for p in $(pgrep -f "build_bundle_pennyroyal|build-penny/rustup|setup_franzen"); do [ "$p" != "$moi" ] && kill "$p" 2>/dev/null; done
sleep 3
cd "$(dirname "$0")/../.." && setsid nohup bash scripts/pod/setup_franzen.sh > /workspace/setup.log 2>&1 < /dev/null &
sleep 5; pgrep -fa "build_bundle_pennyroyal" | cut -c1-80
