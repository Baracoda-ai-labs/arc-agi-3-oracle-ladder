"""Signatures temporelles et délais conditionnels ; jamais une horloge de défaite inventée."""


def resumer(frames, noms):
    visible = [f["controle_visible"] for f in frames]
    # Une perte de reconnaissance n'est ni une preuve de disparition ni une défaite datée.
    pertes = [i for i in range(1, len(frames)) if visible[i - 1] and not visible[i]]
    activations = {n: [i for i, f in enumerate(frames) if f["controle_visible"] and f["regles"][n]["active"]] for n in noms}
    return {
        "activations": activations,
        "premiere_activation": {n: min(v) if v else None for n, v in activations.items()},
        "pertes_reconnaissance": pertes,
        "frames_sans_controle": sum(not x for x in visible),
        "horloge_issue_sdk": "fin_action_seulement",
    }


def delais_compatibles(activations, intervalles, delais_connus=None):
    """Hypothèse explicite : délai fixe entre activation et événement MESURÉ.

    Sans calibration fournie, on expose les délais possibles sans réfuter la règle.
    L'événement peut être visuel : ce n'est alors pas l'instant de défaite SDK.
    """
    if len(activations) != len(intervalles):
        raise ValueError("Tailles incohérentes")
    possibles = None
    for t, intervalle in zip(activations, intervalles, strict=True):
        if t is None or intervalle is None:
            continue
        lo, hi = intervalle
        if lo > hi:
            raise ValueError("Intervalle invalide")
        candidats = set(range(max(0, lo - t), hi - t + 1))
        possibles = candidats if possibles is None else possibles & candidats
    filtres = possibles
    if delais_connus is not None:
        filtres = set(delais_connus) if possibles is None else possibles & set(delais_connus)
    return {
        "delais_conditionnels": None if possibles is None else sorted(possibles),
        "delais_calibres": None if delais_connus is None else sorted(delais_connus),
        "refutation_autorisee": delais_connus is not None and filtres == set(),
        "hypothese_auxiliaire": "même délai non négatif entre activation et événement observé",
    }
