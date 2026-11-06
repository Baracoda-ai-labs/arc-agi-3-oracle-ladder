"""Petites règles terminales composées, filtrées sur films ; aucune identité de jeu."""

import copy
import hashlib
import time

import numpy as np
from agent_p1.experiences import evaluer_candidat
from issues_observees import scene_image

from chrysalide.arc3.langage import Programme
from chrysalide.arc3.sim_rapide import cloner
from chrysalide.langue import depuis_python, vers_python


def regle(controle, cible, relation, effet):
    if relation == "contact_moteur":
        cond = ["contact_moteur", "$a", "$b"]
    elif relation == "proximite_boites":
        cond = [
            "et",
            ["<=", ["x", "$a"], ["+", ["x", "$b"], ["largeur", "$b"]]],
            ["<=", ["x", "$b"], ["+", ["x", "$a"], ["largeur", "$a"]]],
            ["<=", ["y", "$a"], ["+", ["y", "$b"], ["hauteur", "$b"]]],
            ["<=", ["y", "$b"], ["+", ["y", "$a"], ["hauteur", "$a"]]],
        ]
    else:
        raise ValueError("Relation hors grammaire")
    return {
        "mode": "regles",
        "regles": [
            {
                "nom": "consequence_candidate",
                "quand": ["existe", "$a", ["objets", {"tag": controle}], ["existe", "$b", ["objets", {"tag": cible}], cond]],
                "alors": [[effet]],
            }
        ],
    }


def filtrer(programme, episodes):
    p = Programme(programme)
    for numero, (scenes, observe) in enumerate(episodes, 1):
        for frame, sc in enumerate(scenes):
            s = copy.deepcopy(sc)
            p.step(s, ("OBSERVE",))
            if s.issue is not None and s.issue != observe:
                return {"compatible": False, "episode": numero, "frame": frame, "issue_predite": s.issue, "observe": observe}
    return {"compatible": True, "portee": "absence de contradiction sur issues observées, pas loi identifiée"}


class Projection:
    def __init__(self, base, programme):
        self.base = base
        self.programme = programme

    def simuler_seq(self, _etat, seq):
        p = Programme(self.programme)
        traj = []
        for frames in self.base(seq):
            issue = None
            last = None
            for sc in frames:
                s = copy.deepcopy(sc)
                p.step(s, ("OBSERVE",))
                last = s
                if s.issue is not None:
                    issue = s.issue
                    break
            # Hypothèse locale fermée pour comparer ; ne ferme PAS la couverture globale.
            if issue == "defaite":
                obs = ("mort",)
            else:
                obs = (
                    issue or "continue",
                    tuple(
                        (o["x"], o["y"])
                        for o in last.sprites
                        if "controle" in o.get("tags", ()) or any(t.startswith("mobile_") for t in o.get("tags", ()))
                    ),
                )
            traj.append(obs)
            if issue is not None:
                traj.extend([obs] * (len(seq) - len(traj)))
                break
        return traj, None


def proposer(dossier, chaines, local, limite=96, secondes=20, supplementaires=()):
    start = time.monotonic()
    journal = {
        "grammaire": ["contact_moteur", "proximite_boites"],
        "effets": ["perdre", "gagner", "niveau_suivant"],
        "candidats": [],
        "experiences": [],
        "conditions": "géométrie visible et effets terminaux ; pas mécanisme identifié",
        "sdk": 0,
    }
    formal = next(iter(chaines.values()), None)
    if formal is None and local is None:
        return {**journal, "statut": "perception_ou_dynamique_non_admissible"}
    cache = {}
    if formal is not None:
        _check, current = formal.rejouer()
        if current is None:
            return {**journal, "statut": "base_refusee"}
        pc, sc = current
        initial_etat = copy.deepcopy(pc.etat)
        factory = formal.perception.scene
        controls = sorted({t for o in sc.sprites for t in o.get("tags", ()) if t.startswith("mobile_")})
        seqs = [[tuple(a)] for a in formal.actions]
        seqs += [[tuple(a), tuple(b)] for a in formal.actions for b in formal.actions]

        def projection(seq):
            key = str(seq)
            if key not in cache:
                scene, pc.etat = cloner(sc, initial_etat)
                frames = []
                for a in seq:
                    if scene.issue is None:
                        pc.step(scene, a)
                    frames.append([copy.deepcopy(scene)])
                cache[key] = frames
            return cache[key]

        journal["projection"] = "simulateur base Chaine, états après actions"
    else:
        m = local.modele
        factory = lambda image: scene_image(image, m)
        sc = factory(dossier.images[-1])
        controls = ["controle"]
        actions = local.proposer(dossier.images[-1], list(dossier.offre))["experiences_candidates"]
        seqs = [[c["action"]] for c in actions]

        def projection(seq):
            key = str(seq)
            if key not in cache:
                if len(seq) != 1:
                    raise ValueError("Projection locale un coup seulement")
                a = seq[0]
                p = local.predire(dossier.images[-1], a, local.actives()[0])
                s = copy.deepcopy(sc)
                controlled = [o for o in s.sprites if "controle" in o.get("tags", ())]
                if len(controlled) != 1:
                    raise ValueError("Contrôle local ambigu")
                o = controlled[0]
                x, y = m.position(dossier.images[-1])
                ox, oy = p["origine"]
                tx = ox + p["position"][0] * m.pas + m.pas // 2
                ty = oy + p["position"][1] * m.pas + m.pas // 2
                # Supprimer seulement les pixels du bloc cliqué supposé destructible.
                if p["retire"] is not None:
                    rx, ry = p["retire"]
                    left = ox + rx * m.pas
                    top = oy + ry * m.pas
                    for obj in s.sprites:
                        if obj is o:
                            continue
                        for yy, xx in np.argwhere(obj["pixels"] >= 0):
                            if left <= obj["x"] + xx < left + m.pas and top <= obj["y"] + yy < top + m.pas:
                                obj["pixels"][yy, xx] = -1
                frames = []
                # Trajet hypothétique horizontal puis vertical, sans anticiper le défilement.
                for axis, delta in [("x", tx - x), ("y", ty - y)]:
                    for _ in range(abs(delta)):
                        o[axis] += 1 if delta > 0 else -1
                        frames.append(copy.deepcopy(s))
                cache[key] = [frames or [s]]
            return cache[key]

        journal["projection"] = "partielle : déplacement horizontal puis gravité, silhouette conservée ; pas rendu complet"
    if not controls:
        return {**journal, "statut": "controle_non_identifie"}
    tags = sorted({t for o in sc.sprites for t in o.get("tags", ())} - set(controls))
    episodes = [([factory(dossier.images[0])], "continue")]
    try:
        for film, issue in zip(dossier.films, dossier.issues, strict=True):
            episodes.append(([factory(g) for g in film], issue))
    except (ValueError, KeyError, IndexError) as exc:
        return {**journal, "statut": "film_non_interpretable", "raison": repr(exc)}
    journal["frames_sans_controle"] = sum(
        not any(set(o.get("tags", ())) & set(controls) for o in s.sprites) for scenes, _ in episodes for s in scenes
    )
    journal["filtrage"] = "compatibilité visible seulement ; occultations non résolues"
    models = {"sans_regle_additionnelle": Projection(projection, {"regles": []})}
    count = 0
    for control in controls:
        for tag in tags:
            for relation in journal["grammaire"]:
                for effect in journal["effets"]:
                    if count >= limite or time.monotonic() - start > secondes:
                        break
                    p = regle(control, tag, relation, effect)
                    code = vers_python(p)
                    assert depuis_python(code) == p
                    name = hashlib.sha256(code.encode()).hexdigest()[:12]
                    check = filtrer(p, episodes)
                    journal["candidats"].append(
                        {
                            "id": name,
                            "controle": control,
                            "cible": tag,
                            "relation": relation,
                            "effet": effect,
                            "python": code,
                            **check,
                        }
                    )
                    count += 1
                    if check["compatible"]:
                        models[name] = Projection(projection, p)
    for candidat in supplementaires:
        p = depuis_python(candidat["python"])
        check = filtrer(p, episodes)
        journal["candidats"].append({**candidat, **check})
        if check["compatible"]:
            models[candidat["id"]] = Projection(projection, p)
    for seq in seqs:
        if len(seq) > dossier.reserve or time.monotonic() - start > secondes:
            continue
        e = evaluer_candidat(seq, models, dict.fromkeys(models), dict.fromkeys(models, 1))
        predictions = {n: mo.simuler_seq(None, e["seq"])[0] for n, mo in models.items()}
        journal["experiences"].append(
            {
                "actions": e["seq"],
                "evaluation": e,
                "predictions": predictions,
                "statut": "experience_discriminante_simulee" if e["groupes"] > 1 else "sans_information_visible",
                "cout_coups_prefixe": len(e["seq"]),
                "risque_statut": "conditionnel_aux_modeles_et_projection",
                "poids_statut": "uniformes non calibrés",
                "issue_globale": "inconnue",
                "droit_action": False,
            }
        )
    journal.update(
        statut="candidats_filtres",
        generes=count,
        compatibles=len(models) - 1,
        secondes=time.monotonic() - start,
        budget_atteint=count >= limite or time.monotonic() - start > secondes,
    )
    return journal
