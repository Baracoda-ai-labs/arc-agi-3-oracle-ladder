# SPDX-License-Identifier: MIT-0
"""F (charte 21-30, CW-333) : budget de coups dans l'ÉTAT DU PLANIFICATEUR, sous `CHRYS_ECONOMIE` (ALLUMÉ par défaut depuis le 21/10, CW-363.1 ; « 0 » pour l'éteindre).
Pendant une proposition du moteur, `avec_reserve(reserve, cout)` pose la réserve (en coups, lue par
`moteur.reserve_coups`, marge déduite) et le barème ; les planificateurs (`plan.planifier`, `plan_langage.planifier_langage`)
la lisent par `limite()` / `cout(a)` :
- un chemin dont le coût dépasse la réserve n'est plus développé (position perdue : « réserve 0 → défaite ») ;
- **coup gagnant gratuit** : un coup qui gagne est accepté même s'il dépasse la réserve (la victoire, testée d'abord, prime) ;
- **ordre des effets** : victoire avant défaite (un état à la fois gagnant et mortel est une victoire).
Barème (fiche de famille de E, `economie.cout`) : toute_action → chaque action coûte 1 ; mouvements → seuls flèches et SPACE ;
clics → seuls les clics ; aucun → pas de budget ; bareme / inconnu → 1 par action (prudent).
Drapeau éteint ou aucune réserve posée → `limite()` vaut None et rien ne change (contrôle F-C2)."""
import contextvars
import json
import os
from contextlib import contextmanager
from pathlib import Path

import numpy as np

_ECO = contextvars.ContextVar("economie_plan", default=None)
_CACHE = {}  # recherche de barre : échecs (taille d'historique essayée) et niveaux précédents
FICHES = Path(__file__).resolve().parents[3] / "experiments/E_franzen/fiches_familles.json"
MOUVEMENTS = {"UP", "DOWN", "LEFT", "RIGHT", "SPACE", 1, 2, 3, 4, 5}


def allume():
    return os.environ.get("CHRYS_ECONOMIE", "1") == "1"  # allumé par défaut (CW-363.1, 21/10)


def categorie(historique, res=None):
    """Barème pour la recherche (CW-357) : la fiche de famille du jeu d'abord (`categorie_cout`) ; sans fiche (jeu inconnu,
    Kaggle), le barème LU sur la barre (`bareme_observe`) ; « toute_action » à défaut (prudent)."""
    jeu = historique.get("jeu")
    if jeu and categorie_cout(jeu, defaut=None) is not None:
        return categorie_cout(jeu)
    lu, _ = bareme_observe(historique, res)  # `res` : la réserve déjà lue (boîte, couleur, rythme), pas de 2ᵉ recherche
    if lu in ("toute_action", "mouvements", "clics"):
        return lu
    return categorie_qwen(jeu) or "toute_action"  # réponse de Qwen seulement si confirmée ou prudente (CW-357)


def categorie_cout(jeu, defaut="toute_action"):
    """Catégorie `economie.cout` de la fiche de famille du jeu (id court, ex. « re86 ») ; `defaut` sans fiche."""
    if not jeu:
        return defaut
    try:
        fiches = json.loads(FICHES.read_text())["fiches"]
    except Exception:  # noqa: BLE001 — fiche absente : prudent
        return defaut
    court = str(jeu).split("-")[0]
    f = fiches.get(court) if isinstance(fiches, dict) else None
    if f is None and isinstance(fiches, dict):
        f = next((v for v in fiches.values() if isinstance(v, dict) and v.get("jeu") == court), None)
    c = (f or {}).get("economie.cout")
    return defaut if c in (None, "inconnu") else c


def reserve_niveau(historique):
    """Réserve de coups à l'état courant. D'abord sur le niveau en cours (`moteur.reserve_coups`, ≥ 8 coups vus) ; sinon,
    au DÉBUT d'un niveau (politique « après victoire », CW-332), rythme et barre appris sur le niveau précédent du même jeu
    (`precedents`), cases restantes lues sur l'image courante (`moteur.reste_barre`). → dict (statut dit d'où vient la
    réserve) ou None."""
    from chrysalide.arc3.moteur import reserve_coups, reste_barre
    grilles, lots = historique.get("grilles", []), historique.get("lots", [])

    def prudent(r, n, image, statut):
        """Rythme PRUDENT : coups / (cases perdues + 1), comme si une case de plus était entamée. Vérité (20 publics) : le
        rythme brut surestimait la réserve dans 10 points sur 73, surtout tôt (coup 10)."""
        perdu = max(1, round(n / r["rythme"]))
        reste = reste_barre(image, r)
        if reste <= 0:
            return None
        return {**r, "coups": int(reste * n / (perdu + 1)), "coups_brut": r["coups"], "statut": statut}
    if not grilles:
        return None
    if len(_CACHE) > 2000:
        _CACHE.clear()
    precedents = historique.get("precedents", []) or []
    n = len(lots)
    # Coût (B, 7ᵉ vague « rien perdu » : −6,6 % de coups sur PuzzleScript, profil p003 : 16 ms par appel dans
    # `economie.classer`) : la recherche de la barre sur TOUT l'historique, refaite à chaque appel même quand il n'y a
    # pas de barre. Échec mémorisé : nouvel essai seulement quand l'historique a doublé ; niveaux précédents
    # (immuables) lus une fois. Une barre trouvée garde le calcul exact (vérité inchangée).
    cle = ("niveau", hash(np.asarray(grilles[0]).tobytes()), len(precedents))
    essai = _CACHE.get(cle, 0)
    r = None
    if n >= 8 and n >= 2 * essai:
        r = reserve_coups(grilles, n)
        if r is None:
            _CACHE[cle] = n
    if r is not None:
        return prudent(r, n, grilles[-1], "niveau en cours")
    for p in reversed(precedents):
        pg, pl = p.get("grilles", []), p.get("lots", [])
        if not pg:
            continue
        cp = ("precedent", hash(np.asarray(pg[0]).tobytes()), len(pl))
        if cp not in _CACHE:
            _CACHE[cp] = reserve_coups(pg, len(pl))
        rp = _CACHE[cp]
        if rp is not None:
            return prudent(rp, len(pl), grilles[-1], "rythme du niveau précédent")
    return None


def bareme_observe(historique, res=None):
    """« Quelles actions coûtent ? » (CW-357, impasse économie), lu sur la barre : pour chaque coup, la barre a-t-elle
    perdu des cases ? Par sorte d'action (mouvement : flèches et SPACE ; clic), part des coups suivis d'une baisse et
    baisse moyenne. → (catégorie de `economie.cout`, détail) : « toute_action », « mouvements », « clics », ou « inconnu »
    si une sorte n'a pas été assez jouée pour trancher. Sert aussi à VÉRIFIER une réponse de Qwen."""
    from chrysalide.arc3.moteur import reserve_coups, reste_barre
    grilles, lots = historique.get("grilles", []), historique.get("lots", [])
    if res is None:
        res = reserve_coups(grilles, len(lots))
    if res is None or len(grilles) != len(lots) + 1:
        return "inconnu", {}
    cases = [reste_barre(g, res) for g in grilles]
    sortes = {"mouvement": [], "clic": []}
    for t, a in enumerate(lots):
        n = str(a.get("action") if isinstance(a, dict) else (a[0] if isinstance(a, tuple) else a)).upper()
        s = "clic" if n in ("MOUSE", "CLICK", "6") else "mouvement"
        sortes[s].append(max(0, cases[t] - cases[t + 1]))
    detail = {s: {"coups": len(v), "baisse_moyenne": round(sum(v) / len(v), 3) if v else None} for s, v in sortes.items()}
    rythme = res["rythme"]

    def coute(v):  # 1 case tous les `rythme` coups si chaque coup coûte ; < 1/4 de ce taux → gratuit
        if len(v) < max(8, 2 * rythme):
            return None
        return sum(v) / len(v) >= 0.25 / rythme
    m, c = coute(sortes["mouvement"]), coute(sortes["clic"])
    if m is None and c is None:
        return "inconnu", detail
    if m is None:
        return ("clics" if c else "inconnu"), detail
    if c is None:
        return ("toute_action" if m else "clics"), detail  # clics jamais joués : prudence, chaque action coûte
    if m and c:
        return "toute_action", detail
    if m:
        return "mouvements", detail
    return ("clics" if c else "inconnu"), detail


def fonction_cout(categorie):
    def nom(a):  # ("UP", …) du langage, {"action": "UP"} de l'agent, 1-6 du moteur de jeu, chaîne
        if isinstance(a, dict):
            return str(a.get("action") or "").upper()
        return a[0] if isinstance(a, tuple) and a else a

    def est_clic(a):
        return nom(a) in ("CLICK", "MOUSE", 6)
    if categorie == "aucun":
        return None
    if categorie == "mouvements":
        return lambda a: 1 if nom(a) in MOUVEMENTS else 0
    if categorie == "clics":
        return lambda a: 1 if est_clic(a) else 0
    return lambda a: 1


def bilan_plan(actions, reserve_plan):
    """F (CW-410, appui à D) : coût d'un plan au barème et réserve qu'il laisse, pour un outil qui OFFRE un plan
    (inspect_options, plan_borne). reserve_plan = MoteurC.infos["reserve_plan"] ({"coups", "cout", "statut"}) ou None.
    Le dernier coup est gratuit (victoire avant défaite) ; None si la réserve est inconnue ou le jeu sans budget."""
    if not reserve_plan or reserve_plan.get("coups") is None:
        return None
    f = fonction_cout(reserve_plan.get("cout") or "toute_action")
    if f is None:
        return None
    c = sum(f(a) for a in list(actions)[:-1])
    return {"cost": c, "budget_left_after": reserve_plan["coups"] - c, "fits": c < reserve_plan["coups"],
            "costly_actions": reserve_plan.get("cout")}


@contextmanager
def avec_reserve(reserve, categorie="toute_action"):
    """Pose la réserve (coups, entier ≥ 0) et le barème le temps d'une proposition ; sans effet si le drapeau est éteint,
    la réserve inconnue ou le jeu sans budget."""
    f = fonction_cout(categorie)
    jeton = _ECO.set({"reserve": int(reserve), "cout": f}) if allume() and reserve is not None and f is not None else None
    try:
        yield
    finally:
        if jeton is not None:
            _ECO.reset(jeton)


def resserrer(coups):
    """Seconde lecture de la réserve (ex. `th.jauge` de C, CHRYS_JAUGE, avec sa marge) pendant la proposition : la réserve
    en vigueur devient le MINIMUM des deux (CCM-234-C : les deux comptent le même budget ; la sécurité prime tant que la
    lecture de C n'est pas vérifiée sur les 20 publics et T4). Sans réserve posée (drapeau éteint, aucune barre lue par F) :
    sans effet. → réserve en vigueur ou None."""
    e = _ECO.get()
    if e is None or coups is None or not allume():
        return limite()
    e["reserve"] = min(e["reserve"], max(0, int(coups)))
    return e["reserve"]


def limite():
    """Réserve en vigueur (coups) ou None."""
    e = _ECO.get()
    return e["reserve"] if e is not None and allume() else None


def cout(a):
    e = _ECO.get()
    return e["cout"](a) if e is not None else 1


# ------------------------------------------------------------------ impasse « économie » sur `demander_qwen` (CW-357)
MENU_COUT = {"toute_action": "chaque action (flèche, SPACE ou clic) fait baisser la jauge du budget",
             "mouvements": "seuls les déplacements (flèches, SPACE) coûtent ; un clic est gratuit",
             "clics": "seuls les clics coûtent ; flèches et SPACE sont gratuits",
             "aucun": "aucune jauge de budget : rien ne coûte"}
_QWEN = {}  # jeu → {"cout", "signature", "statut"} : réponse de Qwen en attente de vérification par la barre


def dossier_economie(historique):
    """Dossier de la question « quelles actions coûtent ? » : menu fermé, actions jouées et offertes, ce que la barre a
    montré jusqu'ici (sans rien de propre au jeu)."""
    _, det = bareme_observe(historique)
    sortes = {}
    for a in historique.get("lots", []):
        n = str(a.get("action") if isinstance(a, dict) else a).upper()
        sortes[n] = sortes.get(n, 0) + 1
    return {"menu": MENU_COUT, "actions_jouees": sortes, "jauge_observee": det,
            "contrat": "choisir le barème ; il sera vérifié par la baisse de la jauge sur les coups suivants"}


def question_economie(historique, demander=None, **kw):
    """Pose la question SEULEMENT si le barème n'est ni dans la fiche ni lu sur la barre (« inconnu »). `demander` : la
    fonction d'appel (défaut `chrysalide.qwen.demander.demander_qwen`). → réponse, ou None si la question est inutile."""
    jeu = historique.get("jeu")
    if jeu and categorie_cout(jeu, defaut=None) is not None:
        return None
    lu, _ = bareme_observe(historique)
    if lu != "inconnu":
        return None
    if demander is None:
        from chrysalide.qwen.demander import demander_qwen as demander
    rep = demander("economie", dossier_economie(historique), jeu=jeu, **kw)
    if rep.get("statut") == "propose":
        _QWEN[jeu] = {"cout": rep["choix"]["cle"], "signature": rep.get("signature"), "statut": "propose"}
    return rep


def verifier_economie(historique):
    """Réponse de Qwen contre la barre, dès que `bareme_observe` tranche. « confirme » si d'accord ; « refute » sinon (la
    réponse sort du cache de `demander_qwen`). Une réponse non encore vérifiée reste « propose » : elle ne sert que si rien
    d'autre n'est connu, et seulement si elle ne rend gratuite aucune action (prudence, voir `categorie_qwen`)."""
    jeu = historique.get("jeu")
    q = _QWEN.get(jeu)
    if q is None:
        return None
    lu, _ = bareme_observe(historique)
    if lu == "inconnu":
        return q["statut"]
    q["statut"] = "confirme" if lu == q["cout"] else "refute"
    if q["statut"] == "refute" and q.get("signature"):
        from chrysalide.qwen.demander import invalider
        invalider(q["signature"])
    return q["statut"]


def categorie_qwen(jeu):
    """Barème proposé par Qwen, utilisable : confirmé par la barre ; ou proposé et prudent (« toute_action »). Une réponse
    non vérifiée qui rendrait une action gratuite n'est PAS utilisée (elle laisserait le plan dépasser la réserve)."""
    q = _QWEN.get(jeu)
    if q is None or q["statut"] == "refute":
        return None
    if q["statut"] == "confirme" or q["cout"] == "toute_action":
        return q["cout"]
    return None


# ------------------------------------------------------------------ pour le noyau ASP (CW-369/370) : `economie.lp`
LP = Path(__file__).resolve().parent / "economie.lp"


def faits_asp(historique, actions=None, res=None):
    """Faits de l'étage 2 pour `economie.lp` : `reserve0(R).` (réserve lue, marge déduite) et `cout(A, C).` (barème :
    fiche, sinon lu sur la barre). `actions` : noms ASP des actions du domaine (ex. "up", "click_3_4") ; une action dont
    la sorte est gratuite reçoit `cout(a, 0).`. → texte ASP, vide si aucune réserve n'est lue (le plan n'est alors pas borné
    par l'économie : à l'appelant de fixer son horizon)."""
    r = res if res is not None else reserve_niveau(historique)
    if r is None:
        return ""
    lignes = [f"reserve0({max(0, r['coups'] - r['marge'])})."]
    f = fonction_cout(categorie(historique, r))
    for a in actions or ():
        n = str(a).upper()
        lot = {"action": "MOUSE"} if n.startswith(("CLICK", "MOUSE")) else {"action": n}
        if f is not None and f(lot) == 0:
            lignes.append(f"cout({a}, 0).")
    return "\n".join(lignes)
