# SPDX-License-Identifier: MIT-0
"""CW-050 c (session B) : trois changements de consigne, indépendants du jeu, éteints par défaut, dans le harnais de Franzen.
Le patch (scripts/arc3/patcher_consignes.py) appelle `tour(agent, niveau, historique)` au début de
ToolAgent._build_user_prompt ; la fonction rend des lignes à ajouter au message du tour et peut modifier
`agent._system_prompt` (relu ensuite pour la requête). Tout éteint : rend [] et ne touche à rien (règle F-C2).
- CHRYS_EPINGLE=1 : à chaque niveau résolu, ajoute à la consigne système un bloc permanent (hors troncature) : ≤ 30 dernières
  actions gagnantes du niveau + la dernière ligne « World model: » écrite par le modèle (sirikilohit, CW-050).
- CHRYS_AUDIT=1 : une fois par niveau, après CHRYS_AUDIT_ETAPES tours (12) ou CHRYS_AUDIT_MINUTES (30) sans changer de niveau,
  ajoute une consigne d'audit de stratégie ; avec CHRYS_AUDIT_PREDIRE=1, demande en plus une fonction predire(grille, action)
  à vérifier contre l'historique (outil chrys_verifier de A, CCM-059-A).
- CHRYS_LIBELLES=1 : remplace, une fois, la consigne « ne pas se laisser distraire par la barre » par une description honnête
  (la barre est un budget : son épuisement fait échouer l'essai), cohérente avec la règle des drapeaux (rellik13, CW-050)."""
import os
import re
import time

MAX_ACTIONS = 30
TITRE = "\n\n## Solved levels (pinned by the harness; never trimmed)\n"
AUDIT = (
    "STRATEGY AUDIT (once per level): you have spent {etapes} analysis steps / {minutes} min on level {niveau} without "
    "completing it. Before acting again: (1) list in 3 lines what you believe the goal and the rules are; (2) say which of "
    "these beliefs the recent evidence contradicts or never tested; (3) pick ONE cheap experiment that would falsify your "
    "main belief, and run it now."
)
AUDIT_PREDIRE = (
    " Also write `predire(grille, action)` returning the grid you expect after `action`, and check it against the whole "
    "history with `chrys_verifier(predire)` before trusting it."
)
BARRE_FRANZEN = re.compile(
    r"If you identify such a bar, do not get distracted by it or treat it as core gameplay state unless there is "
    r"concrete evidence that it interacts with the puzzle mechanics\."
)
BARRE_HONNETE = (
    "If you identify such a bar, treat it as a budget: when it runs out the attempt fails and the level restarts. "
    "Do not click through its segments, but do count it into your plans."
)


def _on(nom):
    return os.environ.get(nom, "") == "1"


def _ent(nom, defaut):
    try:
        return int(os.environ.get(nom, "") or defaut)
    except ValueError:
        return defaut


def actif():
    return _on("CHRYS_EPINGLE") or _on("CHRYS_AUDIT") or _on("CHRYS_LIBELLES")


def derniere_hypothese(messages):
    """Dernière ligne « World model: … » écrite par le modèle dans l'historique (texte d'assistant)."""
    for m in reversed(messages or []):
        if m.get("role") != "assistant":
            continue
        c = m.get("content") or ""
        c = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict))
        t = re.findall(r"World model:\s*(.+)", c)
        if t:
            return t[-1].strip()[:400]
    return ""


def tour(agent, niveau, historique):
    if not actif():
        return []
    e = agent.__dict__.setdefault("_chrys_consignes", {"niveau": niveau, "depuis": time.monotonic(), "etapes": 0,
                                                       "audit_fait": False, "epingles": set(), "libelles": False})
    lignes = []
    if _on("CHRYS_LIBELLES") and not e["libelles"]:
        agent._system_prompt = BARRE_FRANZEN.sub(BARRE_HONNETE, agent._system_prompt)
        e["libelles"] = True
    if niveau != e["niveau"]:
        resolu = e["niveau"]
        if _on("CHRYS_EPINGLE") and niveau > resolu and resolu not in e["epingles"]:
            acts = [str(h.action) for h in historique if getattr(h, "frame", None) is not None and h.frame.level == resolu]
            hyp = derniere_hypothese(getattr(agent, "_history_messages", []))
            if TITRE not in agent._system_prompt:
                agent._system_prompt += TITRE
            agent._system_prompt += (f"- Level {resolu} solved. Last winning actions: {', '.join(acts[-MAX_ACTIONS:]) or '?'}."
                                     + (f" Your model then: {hyp}" if hyp else "") + "\n")
            e["epingles"].add(resolu)
        e.update(niveau=niveau, depuis=time.monotonic(), etapes=0, audit_fait=False)
    e["etapes"] += 1
    minutes = (time.monotonic() - e["depuis"]) / 60
    if _on("CHRYS_AUDIT") and not e["audit_fait"] and (
            e["etapes"] > _ent("CHRYS_AUDIT_ETAPES", 12) or minutes >= _ent("CHRYS_AUDIT_MINUTES", 30)):
        lignes.append(AUDIT.format(etapes=e["etapes"] - 1, minutes=int(minutes), niveau=niveau)
                      + (AUDIT_PREDIRE if _on("CHRYS_AUDIT_PREDIRE") else ""))
        e["audit_fait"] = True
    return lignes
