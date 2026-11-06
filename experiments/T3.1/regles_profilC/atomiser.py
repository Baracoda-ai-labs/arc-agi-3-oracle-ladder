# SPDX-License-Identifier: MIT-0
"""CW-113/114 : passe « lois atomiques » (OneLife, PoE-World) — chaque règle = une précondition → un effet.
Une règle à n effets devient : une loi déclencheur (précondition → poser t vrai), n lois (t → un effet, dans l'ordre du
fichier, l'effet qui change la liaison ou la précondition placé en dernier par le générateur), une loi t → poser t faux.
Mode ordonné de l'interpréteur (priorité = ordre du fichier), comme le programme d'origine."""


def atomiser(regles, drapeau="t"):
    out = []
    for r in regles:
        alors = r.get("alors", [])
        if len(alors) <= 1:
            out.append(r)
            continue
        base = {k: v for k, v in r.items() if k not in ("quand", "alors", "puis", "nom")}
        t = ["=", ["etat", drapeau], True]
        out.append({**base, "nom": f"{r['nom']} : déclencheur", "quand": r.get("quand", True),
                    "alors": [["poser", drapeau, True]], "puis": "continuer"})
        for i, e in enumerate(alors):
            out.append({**base, "nom": f"{r['nom']} : effet {i + 1}", "quand": t, "alors": [e], "puis": "continuer"})
        out.append({"nom": f"{r['nom']} : fin", "quand": t, "alors": [["poser", drapeau, False]], "puis": r.get("puis", "stop")})
    return out
