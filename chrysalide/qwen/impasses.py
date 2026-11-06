# SPDX-License-Identifier: MIT-0
"""Impasses du moteur branchées sur Qwen (CW-357, CW-362.2) — ÉTEINT par défaut (`CHRYS_QWEN`).
`impasse_regle` : d'abord l'ÉNUMÉRATION déterministe du menu de C (`menu_mecanismes.enumerer` : 15 mécanismes vérifiés par greffe
et rejeu, quelques secondes ; 4/4 sur les parents de la sonde 2, CCM-026-H / CCM-271-C) ; Qwen n'est questionné que si rien n'est
confirmé ET si le drapeau est allumé ; son choix est vérifié de la même façon (jamais utilisé sans `confirme`)."""
from chrysalide.qwen.demander import actif, demander_qwen, reglages


def _menu():
    from chrysalide.arc3.logique import menu_mecanismes  # menu de C, dans le paquet depuis CCM-274-C (embarqué au carnet)
    return menu_mecanismes


def impasse_regle(th, sources, tr, scene, jeu=None):
    """→ {"source": "enumeration" | "qwen" | None, "theorie": théorie greffée | None, "detail": …}."""
    C = _menu()
    conf = C.enumerer(th, sources, tr)
    if conf:
        return {"source": "enumeration", "theorie": conf[0].get("theorie"), "detail": conf[0]}
    if not actif():
        return {"source": None, "theorie": None, "detail": "énumération vide, Qwen éteint"}
    r = demander_qwen("regle", C.dossier(th, tr, scene), jeu=jeu, **reglages())
    if r["statut"] != "propose":
        return {"source": None, "theorie": None, "detail": r}
    cle = r["choix"]["cle"]
    ids = {o["id"]: o for o in scene}
    params = dict(zip(C.MENU[cle]["params"], r["choix"].get("objets", []), strict=False))
    v = C.verifier({"mecanisme": cle, "params": params}, th, sources, tr, ids)
    return {"source": "qwen" if v["statut"] == "confirme" else None, "theorie": v.get("theorie"), "detail": {**v, "qwen": r}}
