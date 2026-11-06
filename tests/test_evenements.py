"""D (CW-324 P0, charte : observations complètes) : un événement distinct par coup — coup, coup sans effet, mort, reset
volontaire, niveau, victoire — avec niveau et vie ; jamais fusionnés."""
from chrysalide.arc3 import branche
from chrysalide.arc3.branche import _evenement

UP, RESET = {"actions": [{"action": "UP"}]}, {"actions": [{"action": "RESET"}]}


def test_evenement_distinct():
    assert _evenement(UP, {}, False, False, False) == "coup"
    assert _evenement(UP, {}, False, False, True) == "coup_sans_effet"
    assert _evenement(UP, {"game_over": True}, False, True, False) == "mort"
    assert _evenement(RESET, {"game_over": True}, False, True, False) == "reset"  # le banc le voit comme une fin de vie
    assert _evenement(UP, {"level_completed": True}, True, False, False) == "niveau"
    assert _evenement(UP, {"level_completed": True, "state": "WIN"}, True, False, False) == "victoire"
    assert _evenement(UP, {"run_complete": True}, True, False, False) == "victoire"


class _Solveur:
    """Solveur minimal : chaque UP change l'image ; la 3ᵉ action finit le niveau, la 5ᵉ tue, la 7ᵉ gagne la partie."""

    def __init__(self):
        self.n, self.g = 0, [[0] * 16 for _ in range(16)]
        self.game = type("J", (), {"game_run": type("R", (), {"game_id": "jouet"})()})()

    def current_frame(self):
        return type("F", (), {"grid": [r[:] for r in self.g]})()

    def step_env(self, arguments):
        self.n += 1
        if str(arguments["actions"][0]["action"]) == "UP":
            self.g[8][8] = self.n % 3 + 1  # case intérieure (le moniteur ignore une bordure)
        return {"executed": True, "level_completed": self.n in (3, 7), "game_over": self.n == 5,
                "state": "WIN" if self.n == 7 else "NOT_FINISHED", "run_complete": self.n == 7}


def test_journal_dans_la_branche(tmp_path, monkeypatch):
    for n in branche.INTERRUPTEURS:
        monkeypatch.delenv(f"CHRYS_{n}", raising=False)
    monkeypatch.setenv("CHRYS_MONITEUR", "1")
    s = _Solveur()
    b = branche.creer(s, tmp_path)
    for a in ("UP", "UP", "UP", "LEFT", "UP", "RESET", "UP"):
        s.step_env({"actions": [{"action": a}]})
    evs = [e["evenement"] for e in b.evenements]
    assert evs == ["coup", "coup", "niveau", "coup_sans_effet", "mort", "reset", "victoire"]
    assert [e["vie"] for e in b.evenements] == [0, 0, 0, 0, 0, 1, 2]
