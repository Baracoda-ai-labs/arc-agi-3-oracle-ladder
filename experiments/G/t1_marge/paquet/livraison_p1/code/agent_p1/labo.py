"""Laboratoire P1 : comme `Laboratoire` v4 (mêmes champs, compatible avec ses agents), mais
- ne s'abstient jamais : jauge non reconnue → réserve supposée de 64 coups par vie (préférence, pas interdiction) ;
- sait jouer RESET (compté comme un coup) après une défaite, pour continuer le même niveau ;
- compte tout : coups, RESET, défaites."""
import json, time
from pathlib import Path
import numpy as np
from boucle_v4.laboratoire import Laboratoire
from boucle_v4.economie import Economie

RESERVE_INCONNUE = 64


class EconomieP1(Economie):
    def __init__(self, image):
        super().__init__(image)
        self.depuis_vie = 0

    def admissible(self, actions):
        if not self.valid or not self.alive.any():
            return self.depuis_vie + len(actions) <= RESERVE_INCONNUE
        return super().admissible(actions)

    def cost_upper(self, actions):
        if not self.valid or not self.alive.any():
            return float(len(actions))
        return super().cost_upper(actions)

    def update(self, a, before, after, terminal=False, won=False):
        self.depuis_vie += 1
        try:
            super().update(a, before, after, terminal, won)
        except Exception as e:  # lecteur hors famille : on garde la réserve supposée
            self.valid = False; self.failures.append(dict(step=self.steps, reason=f'exception lecteur: {e}'))

    def report(self):
        r = super().report(); r['reserve_si_inconnue'] = RESERVE_INCONNUE; return r


class LaboP1(Laboratoire):
    def __init__(self, game, level, jeux, output):
        from chrysalide.arc3.logique.jeux import environnement
        self.env = environnement(game, jeux); f = self.env.reset(); self.injected = level != 1
        self.actions_disponibles = list(getattr(f, 'available_actions', []) or [])
        if self.injected:   # injection de laboratoire (développement seulement), signalée
            self.env._game.set_level(level - 1)
            image = self.env._game.camera.render(self.env._game.current_level.get_sprites())
        else:
            image = f.frame[-1]
        self.image = np.asarray(image); self.images = [self.image.copy()]; self.films = {}; self.rows = []
        self.start = time.monotonic(); self.output = Path(output); self.output.parent.mkdir(parents=True, exist_ok=True)
        self.economy = EconomieP1(self.image); self.completed_baseline = 0
        self.game = game; self.level = level; self.finished = False; self.won = False; self.partie_gagnee = False
        self.defaites = 0; self.resets = 0
        self.save()

    def play(self, a, purpose='experience'):
        from chrysalide.arc3.logique.jeux import jouer_action
        before = self.image.copy()
        f = jouer_action(self.env, tuple(a) if isinstance(a, list) else a)
        self.image = np.asarray(f.frame[-1]); self.images.append(self.image.copy())
        self.films['film_' + str(len(self.rows) + 1)] = np.asarray(f.frame)
        self.actions_disponibles = list(getattr(f, 'available_actions', []) or [])
        self.won = f.levels_completed > self.completed_baseline
        perdu = 'GAME_OVER' in str(f.state)
        self.finished = self.won or perdu
        self.partie_gagnee = 'WIN' in str(f.state)
        self.economy.update(a, before, self.image, self.finished, self.won)
        self.rows.append(dict(step=len(self.rows) + 1, action=a, purpose=purpose, levels_completed=f.levels_completed,
                              state=str(f.state), elapsed=time.monotonic() - self.start))
        if perdu and not self.won:
            self.defaites += 1
        self.save(); return self.image, np.asarray(f.frame)

    def reset_apres_defaite(self, purpose='RESET_apres_defaite'):
        """RESET compté ; le niveau recommence (les niveaux franchis restent acquis)."""
        from chrysalide.arc3.logique.jeux import jouer_action
        f = jouer_action(self.env, 0)
        self.image = np.asarray(f.frame[-1]); self.images.append(self.image.copy())
        self.rows.append(dict(step=len(self.rows) + 1, action=0, purpose=purpose, levels_completed=f.levels_completed,
                              state=str(f.state), elapsed=time.monotonic() - self.start))
        self.resets += 1
        self.completed_baseline = f.levels_completed
        self.finished = False; self.won = False
        self.economy = EconomieP1(self.image)
        self.save(); return self.image

    def next_level(self, output):
        if not self.won:
            raise ValueError('niveau précédent non gagné')
        nxt = object.__new__(LaboP1)
        nxt.env = self.env; nxt.injected = self.injected; nxt.image = self.image.copy(); nxt.images = [nxt.image.copy()]
        nxt.films = {}; nxt.rows = []; nxt.start = time.monotonic(); nxt.output = Path(output)
        nxt.output.parent.mkdir(parents=True, exist_ok=True)
        nxt.economy = EconomieP1(nxt.image); nxt.game = self.game; nxt.level = self.level + 1
        nxt.completed_baseline = self.rows[-1]['levels_completed']; nxt.finished = False; nxt.won = False
        nxt.defaites = 0; nxt.resets = 0; nxt.actions_disponibles = self.actions_disponibles
        nxt.partie_gagnee = False
        nxt.save(); return nxt
