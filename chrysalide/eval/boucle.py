"""Boucle d'appel d'outils par l'agent (T0.8b), sans framework : le modèle émet une ligne JSON {"outil", "args"}, le moteur
du monde l'exécute et la journalise, le résultat revient comme tour « user » ; {"reponse": …} termine. Plafond d'appels fixe."""
import json
import re

from chrysalide.verify.core import Unextractable, extract
from chrysalide.world.engine import run_tool
from chrysalide.world.schema import Tool
from chrysalide.world.surface import norm

CONSIGNE = ("Tu ne connais pas les données : elles ne sont accessibles que par les outils ci-dessous. Pour appeler un outil, "
            "réponds uniquement par une ligne JSON {{\"outil\": \"<nom exact>\", \"args\": {{…}}}} ; tu recevras son résultat. "
            "Un seul appel par message, {n} appels au plus. Quand tu connais la réponse, donne la ligne JSON demandée.\n"
            "Outils disponibles :\n")


def outils_offerts(task, world):
    """Outils de la variante : ceux de la tâche ; pour C3, toutes les fonctions citées dans l'énoncé (leurre compris)."""
    tools = {t["id"]: t for t in world["tools"]}
    ids = list(task["inputs"].get("outils") or task["inputs"].get("tools", []))  # monde v1 : clé « outils » (leurres compris)
    if task["structure_id"] == "C3_composition":
        ids = [t["id"] for t in world["tools"] if t["kind"] == "fonction" and any(f"fonction {t['name']} " in c for c in task["context"])]
    return [tools[i] for i in ids]


def signature(t, noms):
    if t["kind"] == "taux_change":
        devises = ", ".join(noms[e] for e in t["params"]["valeurs"])
        return (f"- \"{t['name']}\" : args {{\"montant\": <entier>, \"de\": \"<devise>\", \"vers\": \"<devise>\"}} ; "
                f"renvoie le montant obtenu, commission déduite. Devises : {devises}.")
    if t["kind"] == "registre":
        return f"- \"{t['name']}\" : args {{\"jour\": <entier>}} ; renvoie le stock à la fin de ce jour."
    return f"- \"{t['name']}\" : args {{\"x\": <entier>}} ; renvoie la valeur de la fonction {t['name']} en x."


def prompt_outil(task, world, n_max):
    noms = {e["id"]: e["name"] for e in world["entities"]}
    offerts = outils_offerts(task, world)
    return CONSIGNE.format(n=n_max) + "\n".join(signature(t, noms) for t in offerts) + "\n\n" + task["question"], offerts


def _visible(out):
    return re.sub(r"^\s*<think>.*?</think>", "", out, count=1, flags=re.DOTALL).strip()


def _appel(out):
    """Ligne JSON {"outil", "args"} stricte, sinon None."""
    s = _visible(out)
    if "\n" in s:
        return None
    try:
        o = json.loads(s)
    except json.JSONDecodeError:
        return None
    return o if isinstance(o, dict) and set(o) == {"outil", "args"} and isinstance(o["args"], dict) else None


def executer(appel, offerts, world):
    """Exécute l'appel par le moteur du monde. Renvoie (résultat, None) ou (None, message d'erreur)."""
    t = next((t for t in offerts if norm(t["name"]) == norm(str(appel["outil"]))), None)
    if t is None:
        return None, f"outil inconnu : {appel['outil']}"
    a = appel["args"]
    try:
        if t["kind"] == "taux_change":
            ids = {norm(e["name"]): e["id"] for e in world["entities"] if e["id"] in t["params"]["valeurs"]}
            dev = lambda v: ids.get(norm(str(v))) or ids.get(norm(str(v)).rstrip("s"))
            args = {"montant": int(a["montant"]), "de": dev(a["de"]), "vers": dev(a["vers"])}
            if None in args.values():
                return None, "devise inconnue"
            v = t["params"]["valeurs"]
            if args["montant"] * v[args["de"]] % v[args["vers"]]:
                return None, "montant non convertible en unités entières"
        elif t["kind"] == "registre":
            args = {"jour": int(a["jour"])}
        else:
            args = {"x": int(a["x"])}
    except (KeyError, TypeError, ValueError) as e:
        return None, f"arguments invalides : {e}"
    journal = []
    return run_tool(Tool(**t), args, journal), None


def conversation(task, texte, offerts, world, n_max, ferme=False):
    """Conversation pas à pas (générateur) : produit la liste de messages à compléter, reçoit (sortie, métriques),
    se termine en renvoyant (sortie finale, totaux). Le même code sert en séquentiel (Mac) et par lots (pod)."""
    msgs, trace = [{"role": "user", "content": texte}], []
    tot = {"tokens_prompt": 0, "tokens_sortie": 0, "mur_s": 0.0, "force": False, "tronque": False}
    out = ""
    for tour in range(n_max + 2):
        out, m = yield list(msgs)
        for k in ("tokens_prompt", "tokens_sortie", "mur_s"):
            tot[k] += m.get(k, 0) or 0
        tot["force"] |= bool(m.get("force")); tot["tronque"] |= bool(m.get("tronque"))
        try:
            extract(out)
            break  # réponse finale au bon format
        except Unextractable:
            pass
        ap = _appel(out) if offerts else None
        if ap is None:
            trace.append({"tour": tour, "valide": False})
            if not offerts or tour > n_max:
                break
            retour = "Format invalide : un appel d'outil ou la ligne JSON de réponse, rien d'autre."
        elif len([x for x in trace if x.get("valide")]) >= n_max:
            trace.append({"tour": tour, "valide": True, "refuse": "plafond"})
            retour = "Plafond d'appels atteint : réponds maintenant par la ligne JSON demandée."
        elif ferme:
            trace.append({"tour": tour, "valide": True, "appel": ap, "erreur": "indisponible"})
            retour = "Outil indisponible."
        else:
            res, err = executer(ap, offerts, world)
            trace.append({"tour": tour, "valide": True, "appel": ap, "resultat": res, "erreur": err})
            retour = f"Erreur : {err}" if err else f"Résultat de {ap['outil']} : {res}"
        msgs += [{"role": "assistant", "content": _visible(out)}, {"role": "user", "content": retour}]
    tot.update({"appels": trace, "n_tours": len(msgs) // 2 + 1})
    return out, tot


def boucle(gen, task, texte, offerts, world, pensant, max_tokens, force, n_max, ferme=False):
    """Déroule une conversation en séquentiel. `ferme` : témoin, les outils sont annoncés mais toujours indisponibles."""
    c = conversation(task, texte, offerts, world, n_max, ferme)
    msgs = next(c)
    while True:
        try:
            msgs = c.send(gen(msgs, pensant, max_tokens, **({"force_reponse": force} if pensant else {})))
        except StopIteration as fin:
            return fin.value


def derouler_lots(convs, gen_lots):
    """Fait avancer toutes les conversations d'un même tour en un seul lot. gen_lots(liste de messages) -> [(sortie, m)]."""
    resultats, actives = [None] * len(convs), {}
    for i, c in enumerate(convs):
        actives[i] = next(c)
    while actives:
        ids = list(actives)
        sorties = gen_lots([actives[i] for i in ids])
        for i, s in zip(ids, sorties, strict=True):
            try:
                actives[i] = convs[i].send(s)
            except StopIteration as fin:
                resultats[i] = fin.value
                del actives[i]
    return resultats
