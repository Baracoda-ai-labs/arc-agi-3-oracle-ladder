"""D (CW-316) : portefeuille de perceptions — la configuration qui rejoue / prédit le mieux est retenue et reste posée ;
égalité → la base ; les réglages d'origine sont rendus à la base."""
import os

from chrysalide.arc3.logique import portefeuille


class _Th:
    def __init__(self, bon):
        self.bon, self.hors_jeu = bon, None


class _Tr:
    exclues = frozenset()


def _faux_rejeu(bons):
    def rejeu(th, tr, debut=0, fin=None, libre=True):
        n = 10 - debut
        return (n if th.bon else n // 2), n, None
    return rejeu


def test_meilleure_config_retenue_et_posee(monkeypatch):
    monkeypatch.delenv("CHRYS_DESOUDER", raising=False)
    monkeypatch.setenv("CHRYS_FORMES", "1")
    portefeuille._BASE.clear()
    import chrysalide.arc3.logique.theorie as T
    monkeypatch.setattr(T, "rejeu", _faux_rejeu(None))

    def percevoir(k=None):  # seule la configuration DESOUDER=1 « explique » l'historique
        return os.environ.get("CHRYS_DESOUDER"), _Tr(), _Th(os.environ.get("CHRYS_DESOUDER") == "1")
    infos = {}
    assert portefeuille.choisir(percevoir, 10, infos) == "1"
    assert os.environ["CHRYS_DESOUDER"] == "1" and os.environ["CHRYS_FORMES"] == "1"
    assert infos["portefeuille"]["retenue"] == {"CHRYS_DESOUDER": "1"} and len(infos["portefeuille"]["scores"]) == 3


def test_egalite_garde_la_base(monkeypatch):
    monkeypatch.delenv("CHRYS_DESOUDER", raising=False)
    monkeypatch.setenv("CHRYS_FORMES", "1")
    portefeuille._BASE.clear()
    import chrysalide.arc3.logique.theorie as T
    monkeypatch.setattr(T, "rejeu", _faux_rejeu(None))
    infos = {}
    r = portefeuille.choisir(lambda k=None: ("base?", _Tr(), _Th(True)), 10, infos)
    assert r == "base?" and infos["portefeuille"]["retenue"] == {}
    assert "CHRYS_DESOUDER" not in os.environ and os.environ["CHRYS_FORMES"] == "1"


def test_configs_par_variable(monkeypatch):
    monkeypatch.setenv("CHRYS_PORTEFEUILLE_CONFIGS", "AMODAL=0;DESOUDER=1,FORMES=0")
    assert portefeuille.configs() == [{}, {"CHRYS_AMODAL": "0"}, {"CHRYS_DESOUDER": "1", "CHRYS_FORMES": "0"}]
