# SPDX-License-Identifier: MIT-0
"""D (CW-422, idées des autres lauréats du jalon 2) : deux ajouts au message de tour de Franzen, chacun derrière sa variable,
ÉTEINTS par défaut (éteint = message de Franzen intact, octet pour octet). Branchés par `scripts/arc3/patcher_conseils.py`
dans `ToolAgent._build_user_message`. Tout se lit sur l'agent (`_last_step_summary`, `_game_elapsed_seconds`,
`_summarized_knowledge`) ; aucune exception ne remonte.
- CHRYS_NIVEAUX_RESOLUS=1 (CW-422.3, sirikilohit) : pour chaque niveau RÉSOLU de la partie, sa règle (la section « world
  model » des notes de Franzen au moment de la victoire, tronquée) et les 30 derniers coups de la vie gagnante, rappelés à
  chaque tour (les 3 derniers niveaux au plus). =2 : TÉMOIN à volume égal (leçon Qwen-horizon de CLAUDE.md : tout bloc injecté a son
  témoin), même longueur, contenu sans rapport avec le jeu.
- CHRYS_REVUE=1 (CW-422.4, lordhansolo) : une seule fois par niveau, quand le niveau courant a consommé 25 % du temps du
  jeu (CHRYS_REVUE_TOTAL_S, sinon MAX_RUNTIME_MINUTES × 60), une consigne de revue de stratégie."""
import os

MAX_NIVEAUX, MAX_COUPS, MAX_REGLE = 3, 30, 400
REVUE = ("STRATEGY REVIEW: this level has already used a quarter of the time budget of the whole game. Before acting, "
         "list the hypotheses you have tested on this level and what each one showed, drop the ones the evidence "
         "contradicts, and choose a different approach from the one you have been repeating.")
_NEUTRE = ("The quick brown fox jumps over the lazy dog while the river keeps flowing past the old mill and the "
           "baker sets out fresh bread on the long wooden table near the window. ")


def _total():
    for cle, f in (("CHRYS_REVUE_TOTAL_S", 1.0), ("MAX_RUNTIME_MINUTES", 60.0)):
        try:
            v = float(os.environ.get(cle, "") or 0) * f
        except ValueError:
            v = 0
        if v > 0:
            return v
    return None


def _nom(a):
    if isinstance(a, dict):
        n = str(a.get("action") or a.get("name") or a)
        if "x" in a or "col" in a:
            n += f"({a.get('x', a.get('col'))},{a.get('y', a.get('row'))})"
        return n
    return str(a)


def _suivre(agent, st):
    s = getattr(agent, "_last_step_summary", None) or {}
    cle = (s.get("start_action_num"), s.get("end_action_num"))
    if not s or s.get("stale") or cle == st["vu"]:
        return
    st["vu"] = cle
    st["tampon"] += [_nom(a) for a in s.get("executed_actions") or []]
    elapsed = float(getattr(agent, "_game_elapsed_seconds", 0.0) or 0.0)
    if s.get("level_transition"):
        regle = str((getattr(agent, "_summarized_knowledge", None) or {}).get("world_model") or "").strip()
        st["resolus"].append({"niveau": max(1, int(s.get("level") or 2) - 1), "regle": regle[:MAX_REGLE],
                              "coups": st["tampon"][-MAX_COUPS:]})
        st["tampon"], st["niv_t0"], st["revue_faite"] = [], elapsed, False
    elif s.get("game_over"):
        st["tampon"] = []  # seule la vie gagnante compte


def _bloc_resolus(st, temoin):
    lignes = ["SOLVED LEVELS in this game (your rule at the time of the win, and the last winning moves):"]
    for r in st["resolus"][-MAX_NIVEAUX:]:
        lignes.append(f"- Level {r['niveau']}: rule: {r['regle'] or '(no note)'} | winning moves: {', '.join(r['coups'])}")
    texte = "\n".join(lignes)
    if temoin:  # même volume, contenu sans rapport
        texte = (_NEUTRE * (len(texte) // len(_NEUTRE) + 1))[:len(texte)]
    return texte


def contexte(agent):
    """Texte à ajouter au message de tour ('' si tout est éteint). Jamais d'exception."""
    niveaux = os.environ.get("CHRYS_NIVEAUX_RESOLUS", "0")
    revue = os.environ.get("CHRYS_REVUE", "0") == "1"
    if niveaux not in ("1", "2") and not revue:
        return ""
    try:
        st = agent.__dict__.setdefault("_chrys_conseils", {"vu": None, "tampon": [], "resolus": [], "niv_t0": 0.0,
                                                           "revue_faite": False})
        _suivre(agent, st)
        parts = []
        if niveaux in ("1", "2") and st["resolus"]:
            parts.append(_bloc_resolus(st, niveaux == "2"))
        total = _total()
        elapsed = float(getattr(agent, "_game_elapsed_seconds", 0.0) or 0.0)
        if revue and total and not st["revue_faite"] and elapsed - st["niv_t0"] >= 0.25 * total:
            st["revue_faite"] = True
            parts.append(REVUE)
        return "\n\n" + "\n\n".join(parts) if parts else ""
    except Exception:  # noqa: BLE001 — un conseil ne doit jamais interrompre le jeu
        return ""
