"""Branchement dans un solveur factice (même interface que framework/solver.py de Franzen : current_frame, step_env)."""
from types import SimpleNamespace

from chrysalide.arc3 import branche


class Solveur:
    """Jeu jouet : UP remplit une case de l'intérieur ; 2 UP finissent le niveau ; le niveau rejoue identique."""
    def __init__(self):
        self.g, self.n, self.appels_modele = [[0] * 64 for _ in range(64)], 0, 0

    def current_frame(self):
        return SimpleNamespace(grid=self.g)

    def step_env(self, arguments):
        fin = False
        for a in arguments["actions"]:
            if a["action"] == "UP":
                self.n += 1
                self.g = [r[:] for r in self.g]
                self.g[10][10 + self.n] = 3
                if self.n == 2:
                    fin, self.n, self.g = True, 0, [[0] * 64 for _ in range(64)]
        return {"executed": True, "level_completed": fin, "game_over": False}

    def jouer_modele(self):
        self.appels_modele += 1
        self.step_env({"actions": [{"action": "UP"}]})


def test_aucun_interrupteur_aucun_branchement(monkeypatch):
    for n in branche.INTERRUPTEURS:
        monkeypatch.delenv(f"CHRYS_{n}", raising=False)
    s = Solveur()
    orig = s.step_env
    assert branche.creer(s) is None and s.step_env == orig  # F-C2 : solveur intact


def test_niveau_appris_puis_rejoue_sans_modele(monkeypatch, tmp_path):
    for n in branche.INTERRUPTEURS:
        monkeypatch.setenv(f"CHRYS_{n}", "1")
    s = Solveur()
    b = branche.creer(s, tmp_path)
    for _ in range(2):  # niveau 1 : le modèle joue
        assert not b.tour()
        s.jouer_modele()
    assert len(b.memoire.reflexes) == 1 and s.appels_modele == 2
    assert s.step_env.__self__ is s  # l'agent de Franzen pose son garde-fou sur step_env.__self__
    assert b.tour() and b.tour()  # niveau identique : rejoué sans modèle
    assert s.appels_modele == 2 and b.bilan()["coups_sans_llm"] == 2 and b.bilan()["reflexes_invalides"] == 0
    assert (tmp_path / "jeu_trace.jsonl").read_text().count('"source": "reflexe"') == 2


def test_surprise_invalide_et_rend_la_main(monkeypatch, tmp_path):
    for n in branche.INTERRUPTEURS:
        monkeypatch.setenv(f"CHRYS_{n}", "1")
    s = Solveur()
    b = branche.creer(s, tmp_path)
    s.jouer_modele()
    s.jouer_modele()
    b._step_original = lambda a: {"executed": True, "level_completed": False, "game_over": False}  # le jeu a changé
    assert b.tour()
    assert b.bilan()["reflexes_invalides"] == 1 and not b.tour()  # réflexe périmé : le modèle reprend


class Couloir(Solveur):
    """UP avance d'une case ; à la 3e case, game over et retour au départ (comme l'auto-reset de Franzen)."""
    def __init__(self):
        super().__init__()
        self.g[10][10] = 3

    def step_env(self, arguments):
        mort = False
        for a in arguments["actions"]:
            if a["action"] == "UP":
                self.n += 1
                if self.n == 3:
                    mort, self.n = True, 0
        self.g = [[0] * 64 for _ in range(64)]
        self.g[10][10 + self.n] = 3
        return {"executed": True, "level_completed": False, "game_over": mort}


def test_graphe_rejoue_jusqu_avant_la_mort(monkeypatch, tmp_path):
    for n in branche.INTERRUPTEURS:
        monkeypatch.delenv(f"CHRYS_{n}", raising=False)
    monkeypatch.setenv("CHRYS_GRAPHE", "1")
    s = Couloir()
    b = branche.creer(s, tmp_path)
    for _ in range(3):  # le modèle joue 3 UP : mort au 3e
        assert not b.tour()
        s.jouer_modele()
    assert b.tour() and b.tour() and not b.tour()  # 2 coups rejoués sans modèle, puis la main au modèle (case 2)
    assert s.n == 2 and s.appels_modele == 3 and b.bilan()["coups_route"] == 2 and b.bilan()["surprises"] == 0


def test_budget_humain_transmis_a_l_agent(monkeypatch, tmp_path):
    from chrysalide.arc3 import outils_repl
    for n in branche.INTERRUPTEURS:
        monkeypatch.delenv(f"CHRYS_{n}", raising=False)
    monkeypatch.setenv("CHRYS_BUDGET", "1")
    s = Solveur()
    s.analyzer = SimpleNamespace()
    s.game = SimpleNamespace(game_run=SimpleNamespace(base_actions_per_level=[30, 50], actions_per_level=[22, 7],
                                                      levels_completed=1))
    b = branche.creer(s, tmp_path)
    assert not b.tour() and s.analyzer._chrys_budget == {"niveau": 2, "h": 50, "a": 7}
    assert "Human reference for level 2: 50 actions; you have used 7" in outils_repl.ligne_tour(s.analyzer)[0]
    s.game.game_run.base_actions_per_level = None  # moteur qui cache h : rien n'est affiché
    b.tour()
    assert s.analyzer._chrys_budget is None and outils_repl.ligne_tour(s.analyzer) == []
