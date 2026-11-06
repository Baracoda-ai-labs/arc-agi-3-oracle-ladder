# SPDX-License-Identifier: MIT-0
"""V2' (CW-040/042) : outils de navigation offerts AU MODÈLE dans le REPL Python de Franzen, calculés sur CPU, sans LLM.

Injectés comme « fonctions retenues » (mécanisme ARC3_PERSISTENT_FUNCTIONS de Franzen) quand CHRYS_OUTILS=1 : aucune
extension du protocole bac à sable ↔ harnais. Chaque source = UNE fonction, sans annotation, défauts littéraux, lisant
seulement les globales du REPL (`history`, `current_frame`, `action`) ou d'autres outils ci-dessous.
Le graphe est reconstruit à chaque appel depuis `history` (frame après chaque coup). États hachés avec le masque appris de
la session B (`masque.py`, recopié ici à l'identique car le REPL ne peut pas importer nos modules ; testé contre lui).
Outils pour le modèle :
  chrys_carte()                 -> résumé : états connus, arêtes, coups mortels, cases masquées (compteurs)
  chrys_chemin(pas)             -> liste d'actions (plus court chemin connu, sans arête mortelle) vers l'état du pas `pas`
  chrys_aller(pas)              -> joue ce chemin avec vérification pas à pas ; s'arrête à la première surprise
  chrys_mortel(a)               -> True si l'action `a` a déjà mené au game over depuis l'état courant"""

CARTE = '''def chrys_carte(detail=False):
    """Map of known states rebuilt from `history` (CPU, no model): hashing masks learned counters/bars."""
    import collections
    entrees = [(str(h.get("action", "") if isinstance(h, dict) else getattr(h, "action", "")),
                h.get("frame") if isinstance(h, dict) else getattr(h, "frame", None),
                dict((h.get("result") if isinstance(h, dict) else getattr(h, "result", None)) or {})) for h in history]
    def grille(f):
        a = f.get("ascii") if isinstance(f, dict) else getattr(f, "ascii", None)
        return [list(r) for r in (a.splitlines() if isinstance(a, str) else a or [])]
    def niveau(f):
        return f.get("level", 0) if isinstance(f, dict) else getattr(f, "level", 0)
    # masque appris (masque.py de B) : zones 8-connexes des cases qui changent ; compteur = fréquent ET jamais revenu
    coups, vie, prec = [], 0, None
    for act, f, res in entrees:
        if f is None:
            continue
        g = grille(f)
        if prec is not None and act.upper() != "RESET" and niveau(prec[1]) == niveau(f) and not res.get("game_over"):
            ch = frozenset((r, c) for r in range(min(len(g), len(prec[0]))) for c in range(min(len(g[r]), len(prec[0][r])))
                           if g[r][c] != prec[0][r][c])
            if ch:
                coups.append((ch, g, vie))
        if act.upper() == "RESET" or res.get("game_over") or (prec is not None and niveau(prec[1]) != niveau(f)):
            vie += 1
        prec = (g, f)
    masque = set()
    if len(coups) >= 8:
        tout = set().union(*(ch for ch, _, _ in coups))
        vu = set()
        for p in sorted(tout):
            if p in vu:
                continue
            pile, z = [p], set()
            vu.add(p)
            while pile:
                r, c = pile.pop()
                z.add((r, c))
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        q = (r + dr, c + dc)
                        if q in tout and q not in vu:
                            vu.add(q)
                            pile.append(q)
            touches = [(g, v) for ch, g, v in coups if ch & z]
            if len(touches) < 0.3 * len(coups):
                continue
            cases = sorted(z)
            if len({(v, tuple(g[r][c] for r, c in cases)) for g, v in touches}) < 0.8 * len(touches):
                continue
            rs, cs, g = {r for r, _ in z}, {c for _, c in z}, touches[-1][0]
            if len(rs) <= 3 and len(cs) >= 4:
                z = z | {(r, c) for r in rs for c in range(len(g[0]))}
            elif len(cs) <= 3 and len(rs) >= 4:
                z = z | {(r, c) for c in cs for r in range(len(g))}
            else:
                continue  # barres seules (correctif de B, CCM-045-B) : une zone qui n'est pas une barre n'est jamais masquée
            masque |= z
    def etat(f):
        g = grille(f)
        return hash((niveau(f), tuple("".join("?" if (r, c) in masque else v for c, v in enumerate(row))
                                     for r, row in enumerate(g))))
    etats, aretes, morts, prec = {}, collections.defaultdict(dict), set(), None
    for pas, (act, f, res) in enumerate(entrees):
        if f is None:
            continue
        s = etat(f)
        etats.setdefault(s, pas)
        if prec is not None and act and act.upper() != "RESET":
            if res.get("game_over"):
                morts.add((prec, act))
            else:
                aretes[prec][act] = s
        prec = None if res.get("game_over") else s
    courant = etat(current_frame)
    carte = {"etats": len(etats), "aretes": sum(len(v) for v in aretes.values()), "coups_mortels": len(morts),
             "cases_masquees": len(masque), "etat_courant_vu_au_pas": etats.get(courant)}
    if detail:
        carte.update({"_etats": etats, "_aretes": aretes, "_morts": morts, "_courant": courant, "_etat": etat,
                      "_pas": {pas: etat(f) for pas, (_, f, _) in enumerate(entrees) if f is not None}})
    return carte
'''

CHEMIN = '''def chrys_chemin(pas):
    """Shortest known action path (never through a known-fatal move) from the current state to the state seen at history[pas]."""
    import collections
    c = chrys_carte(True)
    cible, depart = c["_pas"].get(pas), c["_courant"]
    if cible is None:
        return None
    prec, file = {depart: None}, collections.deque([depart])
    while file:
        s = file.popleft()
        if s == cible:
            chemin = []
            while prec[s] is not None:
                s, a = prec[s]
                chemin.append(a)
            return chemin[::-1]
        for a, t in c["_aretes"].get(s, {}).items():
            if t not in prec and (s, a) not in c["_morts"]:
                prec[t] = (s, a)
                file.append(t)
    return None
'''

ALLER = '''def chrys_aller(pas):
    """Play the known path to the state of history[pas], checking every step; stops at the first surprise."""
    import re
    chemin = chrys_chemin(pas)
    if not chemin:
        return {"joues": 0, "arrive": chemin == [], "raison": "aucun chemin connu" if chemin is None else "deja la"}
    c = chrys_carte(True)
    attendu, joues = c["_courant"], 0
    for a in chemin:
        attendu = c["_aretes"][attendu][a]
        m = re.match(r"MOUSE\\(row=(-?\\d+), col=(-?\\d+)\\)", a)
        action({"action": "MOUSE", "row": int(m.group(1)), "col": int(m.group(2))} if m else a)
        joues += 1
        if c["_etat"](current_frame) != attendu:
            return {"joues": joues, "arrive": False, "raison": "surprise : etat observe different de l'etat prevu"}
    return {"joues": joues, "arrive": True}
'''

MORTEL = '''def chrys_mortel(a):
    """True if action `a` (e.g. "UP" or "MOUSE(row=3, col=7)") already led to game over from the current state."""
    c = chrys_carte(True)
    return (c["_courant"], str(a)) in c["_morts"]
'''

VERIFIER = '''def chrys_verifier(predire, debut=0, fin=None, bord=4):
    """Check YOUR rule predire(grid, action) -> next grid against every observed transition in `history` (CPU, free).
    grid = list of rows, each a list of 1-char cells as in current_frame.ascii; action = history string ("UP",
    "MOUSE(row=3, col=7)"). Cells within `bord` of the edge (bars, counters) are ignored. Returns exactitude (share of
    transitions predicted exactly), the first contradicted step with up to 5 wrong cells (row, col, predicted, observed)."""
    def grille(f):
        a = f.get("ascii") if isinstance(f, dict) else getattr(f, "ascii", None)
        return [list(r) for r in (a.splitlines() if isinstance(a, str) else a or [])]
    def champ(h, k):
        return h.get(k) if isinstance(h, dict) else getattr(h, k, None)
    justes, total, premiere, prec = 0, 0, None, None
    for pas, h in enumerate(history):
        act, f, res = str(champ(h, "action") or ""), champ(h, "frame"), dict(champ(h, "result") or {})
        if f is None:
            prec = None
            continue
        g1 = grille(f)
        if (prec is not None and act and act.upper() != "RESET" and not res.get("game_over") and pas >= debut
                and (fin is None or pas < fin)):
            total += 1
            try:
                p = [list(r) for r in predire([r[:] for r in prec], act)]
                erreur = None
            except Exception as e:
                p, erreur = None, type(e).__name__ + ": " + str(e)[:80]
            fausses = [] if p is None else [(r, c, p[r][c] if r < len(p) and c < len(p[r]) else None, g1[r][c])
                                            for r in range(bord, len(g1) - bord) for c in range(bord, len(g1[r]) - bord)
                                            if r >= len(p) or c >= len(p[r]) or p[r][c] != g1[r][c]]
            if p is not None and not fausses:
                justes += 1
            elif premiere is None:
                premiere = {"pas": pas, "action": act, "erreur": erreur, "cases_fausses": fausses[:5],
                            "n_cases_fausses": len(fausses)}
        prec = None if res.get("game_over") else g1
    return {"transitions": total, "exactes": justes, "exactitude": round(justes / total, 3) if total else None,
            "premiere_contradiction": premiere}
'''

SOURCES = [CARTE, CHEMIN, ALLER, MORTEL]
if __import__("os").environ.get("CHRYS_VERIFIER", "0") == "1":  # interrupteur à part : V2p (CHRYS_OUTILS seul) inchangé
    SOURCES.append(VERIFIER)

CONSIGNE = ("Navigation tools (CPU, no cost to you), always available: chrys_carte() summarises the states you have seen; "
            "chrys_chemin(step) returns the shortest known move list from here back to the state at history[step]; "
            "chrys_aller(step) plays it with step-by-step checks (stops on any surprise); chrys_mortel(a) tells if move a "
            "already caused a game over from this exact state. Use them to return to a known position instead of "
            "re-deriving moves.")


def coups_niveau(agent):
    """Coups joués depuis le début du niveau courant, lus dans l'agent de Franzen (0 si inconnu)."""
    import sys
    try:
        compte = sys.modules.get("inference.agent.tool_agent")._priority_action_count
        resume = getattr(agent, "_last_step_summary", None)
        return compte(resume) - int(getattr(agent, "_actions_at_level_start", 0)) if resume else 0
    except Exception:  # noqa: BLE001 — version de Franzen inattendue : aucun déclenchement
        return 0


def outils_actifs(agent):
    """CHRYS_OUTILS=1 ; si CHRYS_OUTILS_APRES=N > 0, seulement après N coups sans finir le niveau (stagnation) :
    les outils n'alourdissent pas les niveaux que Franzen résout vite. N absent ou 0 = toujours (V2' inchangé)."""
    import os
    if os.environ.get("CHRYS_OUTILS", "0") != "1":
        return False
    apres = int(os.environ.get("CHRYS_OUTILS_APRES", "0") or 0)
    return apres <= 0 or coups_niveau(agent) >= apres


def ligne_tour(agent):
    """Texte ajouté au message de tour par le patch outils : consigne des outils (CHRYS_OUTILS) et, si CHRYS_BUDGET=1,
    « budget humain » du niveau (CW-080.5) ; si CHRYS_MOTEUR=1, ligne d'état de la théorie vérifiée et consigne du
    déclencheur posées par branche.py. Rien si les trois sont éteints (Franzen inchangé)."""
    import os
    parts = []
    if outils_actifs(agent):
        parts.append(CONSIGNE)
    b = getattr(agent, "_chrys_budget", None)
    if os.environ.get("CHRYS_BUDGET", "0") == "1" and b:
        parts.append(f"Human reference for level {b['niveau']}: {b['h']} actions; you have used {b['a']}. "
                     "Each action beyond the human count lowers this level's score quadratically.")
    if os.environ.get("CHRYS_MOTEUR", "0") == "1":  # CW-134 P10 : attributs d'état de la théorie vérifiée (branche.py),
        for k in ("_chrys_etat", "_chrys_consigne"):  # puis consigne du déclencheur (CW-133, rappels muets par défaut)
            t = getattr(agent, k, None)
            if t:
                parts.append(t)
    return parts
