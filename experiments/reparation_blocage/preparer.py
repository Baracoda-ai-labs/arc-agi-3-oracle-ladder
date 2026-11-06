"""Construit une copie expérimentale vérifiable du paquet v3, sans toucher la référence."""
import hashlib
import shutil
from pathlib import Path

ICI = Path(__file__).resolve().parent
REF = ICI.parent / "GEL27_moteur_seul_v3"
PAQUET = ICI / "paquet"


def preparer():
    if not PAQUET.exists():
        shutil.copytree(REF, PAQUET)
    original = REF / "livraison_p1/code/agent_p1/releve_moteur.py"
    source = original.read_text()
    appel = "    from chrysalide.arc3.moteur import MoteurC, _code_c, nom_action, porte\n"
    assert source.count(appel) == 1
    source = source.replace(appel, "    if os.environ.get('CHRYS_CHAINE_COHERENTE') == '1':\n"
                            "        from .releve_coherent import tenter as coherent\n"
                            "        return coherent(ex, mode)\n"
                            "    if os.environ.get('CHRYS_REPARATION_BLOCAGE') == '2':\n"
                            "        from .reparation_locale import tenter as reparer\n"
                            "        return reparer(ex, mode)\n"
                            "    if os.environ.get('CHRYS_REPARATION_BLOCAGE') == '1':\n"
                            "        from .reparation_blocage import tenter as reparer\n"
                            "        return reparer(ex, mode)\n" + appel)
    (PAQUET / original.relative_to(REF)).write_text(source)
    shutil.copy2(ICI / "code/reparation_blocage.py", PAQUET / "livraison_p1/code/agent_p1/reparation_blocage.py")
    shutil.copy2(ICI / "code/reparation_locale.py", PAQUET / "livraison_p1/code/agent_p1/reparation_locale.py")
    shutil.copy2(ICI / 'chaine_coherente.py', PAQUET / 'livraison_p1/code/agent_p1/chaine_coherente.py')
    shutil.copy2(ICI / 'montecarlo.py', PAQUET / 'livraison_p1/code/agent_p1/montecarlo.py')
    for nom in ('atms.py', 'cegar.py', 'cegar_compile.py'):
        shutil.copy2(ICI / nom, PAQUET / 'livraison_p1/code/agent_p1' / nom)
    shutil.copy2(ICI / 'evidence_films.py', PAQUET / 'livraison_p1/code/agent_p1/evidence_films.py')
    shutil.copy2(ICI / 'code/releve_coherent.py', PAQUET / 'livraison_p1/code/agent_p1/releve_coherent.py')
    shutil.copy2(ICI / 'bilan_skos_shacl.json', PAQUET / 'livraison_p1/code/agent_p1/bilan_skos_shacl.json')
    moteur = REF / "chrysalide/arc3/moteur.py"
    texte = moteur.read_text()
    retour = "                return [_lot_c(a, tr) for a in plan], prog"
    assert texte.count(retour) == 2
    texte = texte.replace(retour, "                if (os.environ.get('CHRYS_REPARATION_BLOCAGE') == '2'\n"
                          "                        or os.environ.get('CHRYS_CHAINE_COHERENTE') == '1'):\n"
                          "                    self.th_plan = c\n" + retour)
    (PAQUET / moteur.relative_to(REF)).write_text(texte)
    export = REF / 'chrysalide/arc3/logique/export_langage.py'
    texte = export.read_text()
    ancien = '''    for c, a, x0, y0 in getattr(th, "retour", ()):  # C (g50t) : sous l'action, le mobile revient à sa position de départ
        regles.append({"nom": f"retour c{c} {NOMS.get(a, a)}", "phase": 0.7, "quand": ["=", ["action"], NOMS.get(a, a)],'''
    nouveau = '''    for c, a, x0, y0 in getattr(th, "retour", ()):  # C (g50t) : sous l'action, le mobile revient à sa position de départ
        quand = ["=", ["action"], NOMS.get(a, a)]
        if os.environ.get("CHRYS_EXPORT_SANS_EFFET") == "1" and th.sans_effet:
            quand = ["et", quand, ["!=", ["etat", "_sans_effet"], True]]
        regles.append({"nom": f"retour c{c} {NOMS.get(a, a)}", "phase": 0.7, "quand": quand,'''
    assert texte.count(ancien) == 1
    (PAQUET / export.relative_to(REF)).write_text(texte.replace(ancien, nouveau))
    theorie = REF / 'chrysalide/arc3/logique/theorie.py'
    texte = theorie.read_text()
    needle = '    return [z for z, k in col.items() if k not in marques\n'
    assert texte.count(needle) == 1
    texte = texte.replace(needle, '    if os.environ.get("CHRYS_CENTRES_RAPIDES") == "1":\n'
                          '        from chrysalide.arc3.logique.centres_rapides import centres_motifs as rapides\n'
                          '        return rapides(col, marques)\n' + needle)
    (PAQUET / theorie.relative_to(REF)).write_text(texte)
    shutil.copy2(ICI / 'code/centres_rapides.py', PAQUET / 'chrysalide/arc3/logique/centres_rapides.py')
    plan = REF / 'chrysalide/arc3/logique/plan.py'
    texte = plan.read_text()
    ancien = '    if th.motif:  # jeux à clic'
    assert texte.count(ancien) == 1
    texte = texte.replace(ancien, '    if th.motif or (th.sans_effet and os.environ.get("CHRYS_PLAN_CONTEXTE_COMPLET") == "1"):  # jeux à clic')
    (PAQUET / plan.relative_to(REF)).write_text(texte)
    portefeuille = Path('chrysalide/arc3/logique/plan_portefeuille.py')
    shutil.copy2(ICI.parents[1] / portefeuille, PAQUET / portefeuille)
    # Correctif de métadonnées déjà acquis par B : même source que les vues SKOS/SHACL.
    ontologie = Path('chrysalide/langue/ontologie_formelle.py')
    shutil.copy2(ICI.parents[1] / ontologie, PAQUET / ontologie)
    contrats = ontologie.with_name('theorie_contrats.py')
    shutil.copy2(ICI.parents[1] / contrats, PAQUET / contrats)
    qwen = Path('chrysalide/qwen/demander.py')
    shutil.copy2(ICI.parents[1] / qwen, PAQUET / qwen)
    noms = [line.split(maxsplit=1)[1] for line in (REF / "SHA256SUMS").read_text().splitlines()]
    noms.append("livraison_p1/code/agent_p1/reparation_blocage.py")
    noms.append("livraison_p1/code/agent_p1/reparation_locale.py")
    noms.append('chrysalide/arc3/logique/centres_rapides.py')
    noms += ['livraison_p1/code/agent_p1/' + n for n in
             ('chaine_coherente.py', 'montecarlo.py', 'atms.py', 'cegar.py', 'cegar_compile.py', 'evidence_films.py', 'releve_coherent.py', 'bilan_skos_shacl.json')]
    manifest = "".join(f"{hashlib.sha256((PAQUET / n).read_bytes()).hexdigest()}  {n}\n" for n in sorted(noms))
    (PAQUET / "SHA256SUMS").write_text(manifest)
    sha = hashlib.sha256(manifest.encode()).hexdigest()
    (PAQUET / "EMPREINTE.txt").write_text(f"Copie expérimentale : v3 + reprise après blocage, jamais soumise.\nglobal {sha}\n")
    return sha


if __name__ == "__main__":
    print(preparer())
