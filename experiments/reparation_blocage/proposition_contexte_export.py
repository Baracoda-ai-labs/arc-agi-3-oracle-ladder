"""Prépare le diff sans modifier le runtime ; également utilisé par les tests."""
from pathlib import Path
import difflib
import types

R = Path(__file__).parent
REMPLACEMENTS = {
    'revision_perception_selection.py': [
        ('    th, tr = vue.th_releve, vue.tr\n',
         "    vue.contexte_export = {**getattr(vue, 'contexte_export', {}), 'CHRYS_PORTEUR_BOITE': '1'}\n    th, tr = vue.th_releve, vue.tr\n")],
    'buts_modele_conserve.py': [
        ('from chrysalide.arc3.logique.export_langage import exporter\n',
         'from contexte_export import exporter_contextuel\n'),
        ('exporter(th, vue.tr.taille)', 'exporter_contextuel(vue, th, vue.tr.taille)'),
        ('exporter(perception.th_releve, tr.taille)',
         'exporter_contextuel(perception, perception.th_releve, tr.taille)')],
    'transfert_modele_c.py': [
        ('from chrysalide.arc3.logique.export_langage import exporter\n',
         'from contexte_export import exporter_contextuel\n'),
        ('exporter(origine, ancien.taille)', 'exporter_contextuel(vue, origine, ancien.taille)'),
        ('    m = MoteurC()\n', "    m = MoteurC()\n    m.contexte_export = copy.deepcopy(getattr(vue, 'contexte_export', {}))\n"),
        ('exporter(th, tr.taille)', 'exporter_contextuel(m, th, tr.taille)')],
}


def contenu_propose(nom):
    texte = (R/nom).read_text()
    for ancien, nouveau in REMPLACEMENTS[nom]:
        assert texte.count(ancien) == 1, (nom, ancien)
        texte = texte.replace(ancien, nouveau)
    return texte


def charger_proposition(nom):
    module = types.ModuleType('proposition_' + Path(nom).stem)
    module.__file__ = str(R/nom)
    exec(compile(contenu_propose(nom), str(R/nom), 'exec'), module.__dict__)
    return module


if __name__ == '__main__':
    resultat = ''
    for nom in REMPLACEMENTS:
        chemin = 'experiments/reparation_blocage/' + nom
        resultat += ''.join(difflib.unified_diff((R/nom).read_text().splitlines(True),
                                                contenu_propose(nom).splitlines(True),
                                                fromfile='a/'+chemin, tofile='b/'+chemin))
    (R/'PROPOSITION_CONTEXTE_EXPORT.patch').write_text(resultat)
    print('Patch préparé, non appliqué : PROPOSITION_CONTEXTE_EXPORT.patch')
