"""Consensus, buts candidats hérités et statut explicite du retrait."""

from types import SimpleNamespace

from branche_retour import retour
from experience_bfws import ExperienceLocale
from experience_regles_bp35 import cle
from perception_hierarchique import decomposer
from plan_consensus import chercher_modele


def decision(image, h, cs, known, remaining, offre=(3, 4, 6)):
    if not cs:
        return {"plan": None, "raison": "couverture_absente"}
    g = h.catalogue[h.actives()[0]][0]
    try:
        buts = set(map(tuple, h.modele.proposer(image, gravite=g)["buts_hypothetiques"]))
    except ValueError:
        buts = set()

    def scene(im):
        p, o, free, blocks = h.scene(im)
        return p, o, free | buts, blocks

    local = SimpleNamespace(modele=h.modele, actives=h.actives, catalogue=h.catalogue, scene=scene)
    model = ExperienceLocale(image, local, cs, offre, horizon=24, scene_factory=lambda im, m: decomposer(im, m)[0])
    bans = {
        str(list(a) if isinstance(a, tuple) else a)
        for a in model.actions(model.depart)
        if cle(image, list(a) if isinstance(a, tuple) else a) in known
    }
    model.horizon = min(12, remaining)
    result = chercher_modele(model, bans, buts=buts)
    cur = model.depart
    steps = []
    for a in result["plan"] or []:
        cur = model.pas(cur, a)
        steps.append({"position": cur[0], "predictions": dict(zip(cs, cur[2], strict=True))})
    result.update(
        etapes=steps, buts_candidats=sorted(buts), raison="remontee_consensus" if result["plan"] else "aucun_progres_consensus"
    )
    if result["plan"]:
        t = model.pas(model.depart, result["plan"][0])
        model.horizon = 24
        back = retour(model, t, model.start)
        edge = min(y for x, y in model.free | model.blocks) if g < 0 else max(y for x, y in model.free | model.blocks)
        suite = len(result["plan"]) > 1 or t[0] in buts or t[0][1] == edge
        result.update(retour_apres_action=back, engagement_sans_retour=back is None, suite_ou_frontiere=suite)
        if back is None and not suite:
            result.update(plan=None, raison="engagement_sans_suite_visible_refuse")
    return result
