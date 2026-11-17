"""Bonus Stage 3 sections 1 and 4 played by looking at the platforms, not in the original.

The original jumps on fixed timings (BonusStage3Section1/4 in BonusStage.au3). On this game version (2026-11-16,
nine stages recorded) those timings drift off the layout: section 1 lost its 4th pillar in all 4 tries and
section 4 stood against walls. This module reads the platforms and the player on every grab and decides each
jump from where the next platform is and how fast the terrain moves.

Measured 2026-11-16 (client coordinates):
- A platform's top edge is B9BBFC with 151515 three rows above; its body (light, BODY_DY px lower) gives its
  width, which the player's boost trail can't hide.
- The player stays at client x ~40-135; its magenta (any shade: darker for a while after a fall) is the only
  magenta left of x 170. Running, the trail starts at x < 70; in the air it starts at x >= 71.
- The terrain scrolls ~485 px/s; with the boost (trail out to x >= 160) ~900 px/s, and section 4 runs at ~880.
- A fall costs ~2 s and respawns the player before the stretch it fell in. There is no double jump.
"""
import logging

import numpy as np

from idle_runner.game import Game
from idle_runner.log import event

log = logging.getLogger(__name__)

Platform = tuple[int, int, int]  # left, right, top y
Box = tuple[int, int, int, int]  # left, right, top, bottom

PLAYER_X = 110          # client x under the player's feet
FRONT = 140             # platforms starting right of this are ahead of the player
LAND_IN = 35            # land this far into a platform
EDGE_MARGIN = 25        # the last moment to jump: the platform's end this close past PLAYER_X
SPEED = 485             # px/s, normal terrain speed; never plan with less
BOOST_SPEED = 900       # px/s while the boost trail shows (measured 880-980)
DROP_S = 0.32           # a ~206 px drop off an edge
BODY_DY = 15            # the row below a top edge that gives the platform's width
MIN_GAP_S = 0.3         # between two jumps
SECOND_WIND_AFTER_MS = 3000  # the fail screen of the last section can still be up when a rerun starts
SECOND_WIND_SETTLE_MS = 1000  # its button ignores clicks while the dialog slides in
HOLD_MS = {"up": 150, "same": 80, "down": 80, "long": 200, "wall": 300}
# Seconds in the air until the feet are back at a platform dy px higher (negative: lower), by hold. Measured:
# hold 150 up 206 -> 0.62 (S1), up 103 -> ~0.80 (S4, it flew over a 96 px step); hold 80 level -> 0.70, down 103
# -> 0.90 (S1, boosted). The rest is extrapolated.
AIR_BY_HOLD = {150: ((206, 0.62), (103, 0.80), (0, 0.92), (-206, 1.10)),
               80: ((103, 0.55), (0, 0.70), (-103, 0.90), (-206, 1.05))}
BANNER = (342, 41, 934, 80)  # client box of "Section Completed!" (bonus_stage.REWARD_BAND)
BANNER_WHITE_MIN = 3000      # the banner: 4035 white px; the orb counter and orb glints: 360-1253
ORB = (0x25, 0xE2, 0xCD)


def platforms(img: np.ndarray) -> list[Platform]:
    """Every platform on screen, sorted by left edge."""
    top = (img[3:, :, 0] == 0xB9) & (img[3:, :, 1] == 0xBB) & (img[3:, :, 2] == 0xFC)
    dark = (img[:-3, :, 0] == 0x15) & (img[:-3, :, 1] == 0x15) & (img[:-3, :, 2] == 0x15)
    edge = top & dark
    found: list[Platform] = []
    rows_seen: list[int] = []
    for y in np.nonzero(edge.sum(axis=1) > 15)[0]:
        if any(abs(y - seen) <= 4 for seen in rows_seen):
            continue  # the same top edge, one row lower
        rows_seen.append(y)
        light = img[min(y + 3 + BODY_DY, img.shape[0] - 1)].min(axis=1) > 0x70
        xs = np.nonzero(light)[0]
        edge_xs = np.nonzero(edge[y] | edge[min(y + 1, edge.shape[0] - 1)])[0]
        for run in np.split(xs, np.nonzero(np.diff(xs) > 8)[0] + 1) if len(xs) else []:
            if len(run) > 15 and ((edge_xs >= run[0]) & (edge_xs <= run[-1])).sum() > 10:
                found.append((int(run[0]), int(run[-1]), int(y + 3)))
    return sorted(found)


def player(img: np.ndarray) -> Box | None:
    sub = img[:, :170].astype(np.int16)
    magenta = (sub[:, :, 0] > 0x90) & (sub[:, :, 1] < 0x70) & (sub[:, :, 2] > 0xB0) & (sub[:, :, 0] - sub[:, :, 1] > 0x60)
    ys, xs = np.nonzero(magenta)
    if len(xs) < 100:
        return None
    return int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())


def section_done(img: np.ndarray) -> bool:
    x0, y0, x1, y1 = BANNER
    return int((img[y0:y1, x0:x1] == 255).all(axis=2).sum()) >= BANNER_WHITE_MIN


def banner_up(game: Game) -> bool:
    x0, y0, x1, y1 = BANNER
    box = game.grab(x0 + game.ox, y0 + game.oy, x1 - 1 + game.ox, y1 - 1 + game.oy)
    return int((box == 255).all(axis=2).sum()) >= BANNER_WHITE_MIN


def wait_reward_cleared(game: Game, timeout_ms: float = 15_000, after_ms: float = 1000) -> None:
    """Until the last section's banner is gone, then after_ms more: its reward loot (gems with white glints) is
    still crossing the screen when the banner goes."""
    deadline = game.now() + timeout_ms
    while banner_up(game) and game.now() < deadline:
        game.sleep(100)
    game.sleep(after_ms)


def orbs_above(img: np.ndarray, top: int) -> int:
    """Orb pixels hanging over the platform ahead of the player (section 4's grids over the tall blocks); orbs
    resting on a platform (top-50..top-5) don't count."""
    box = img[max(top - 260, 0):max(top - 60, 0), PLAYER_X:PLAYER_X + 200]
    return int((box == ORB).all(axis=2).sum())


class Speed:
    """Terrain speed in px/s: fully visible platforms against the grabs 120-300 ms old (the median).

    A grab is sometimes a stale picture (the game hasn't redrawn the window yet): against the previous grab that
    reads as no motion, and dragged the estimate to 170-450 px/s (2026-11-16 19:33)."""

    def __init__(self) -> None:
        self.value = float(SPEED)
        self.history: list[tuple[float, list[Platform]]] = []

    def update(self, t: float, plats: list[Platform], width: int) -> float:
        whole = [p for p in plats if p[0] > 3 and p[1] < width - 4]
        self.history = [(ht, hp) for ht, hp in self.history if t - ht <= 0.3]
        estimates = []
        for ht, old in self.history:
            if t - ht < 0.12:
                continue
            shifts = []
            for p in whole:  # the same platform: same width, the nearest one right of it then
                cands = [q[0] - p[0] for q in old if abs((q[1] - q[0]) - (p[1] - p[0])) <= 4 and q[0] >= p[0]]
                if cands:
                    shifts.append(min(cands))
            if shifts:
                estimates.append(float(np.median(shifts)) / (t - ht))
        if estimates:
            self.value = float(np.median(estimates))
        self.history.append((t, whole))
        return self.value


def air_time(kind: str, dy: int, hold: int | None = None) -> float:
    table = AIR_BY_HOLD[hold or (150 if kind == "up" else 80)]
    heights, times = [d for d, _ in reversed(table)], [s for _, s in reversed(table)]
    return float(np.interp(dy, heights, times))


def jump_kind(ground: Platform, target: Platform) -> str:
    dy = ground[2] - target[2]  # > 0: the target is higher
    return "up" if dy > 60 else "down" if dy < -60 else "same"


def plan(ground: Platform, plats: list[Platform], v: float) -> tuple[str | None, str, Platform | None]:
    """("jump" | "wait" | "drop", kind, target) for the nearest platform ahead that can be reached, or
    (None, "same", None).

    A jump lands at PLAYER_X + v * air time: the target's left must have passed that point by LAND_IN and its right
    not yet (20 px margin), after some scroll d between now and this platform's end. A lower platform is reached by
    walking off the edge when the drop lands on it."""
    edge_d = ground[1] - (PLAYER_X + EDGE_MARGIN)
    for p in [p for p in plats if p[0] > FRONT and p != ground]:
        kind = jump_kind(ground, p)
        if kind == "down":
            off = ground[1] - PLAYER_X  # the feet leave the edge after this much scroll
            land = PLAYER_X + v * DROP_S
            if p[0] - off <= land - 20 and p[1] - off >= land + 20:
                return "drop", kind, p
        land = PLAYER_X + v * air_time(kind, ground[2] - p[2])
        d_min, d_max = p[0] - land + LAND_IN, p[1] - land - 20
        if d_max < 0 or d_min > max(edge_d, 0):
            continue  # overshot already, or still out of reach at the edge
        return ("jump" if d_min <= 0 else "wait"), kind, p
    return None, "same", None


def high_jump_lands(ground: Platform, plats: list[Platform], v: float) -> Platform | None:
    """A platform (this one included) that a 150 ms jump made now lands on."""
    for p in [ground] + [p for p in plats if p[0] > FRONT and p != ground]:
        land = PLAYER_X + v * air_time("up", ground[2] - p[2], hold=150)
        if p[0] - land + LAND_IN <= 0 <= p[1] - land - 20:
            return p
    return None


def standing_on(pl: Box | None, plats: list[Platform]) -> Platform | None:
    """The platform under a running or standing player. Standing still against a wall the trail leaves the feet:
    the magenta then ends ~45 px above the top."""
    if pl is None or pl[0] >= 70:
        return None
    under = [p for p in plats if p[0] <= 130 and p[1] >= 80 and -5 <= p[2] - pl[3] <= 55]
    return under[0] if under else None


def play_section(game: Game, label: str, max_ms: float, hops: bool = False) -> None:
    """Jump from platform to platform until the "Section Completed!" banner, the fail screen's Second Wind (left
    for bs3_fail to click) or max_ms. With `hops`, also jump through orb grids over the platform (section 4)."""
    w, h = game.size
    begin = game.now()
    speed = Speed()
    last_jump = -1e9
    last_ground: Platform | None = None
    last_ground_t = 0.0
    jumps, end = 0, "time"
    while game.now() - begin < max_ms:
        if game.now() - begin > SECOND_WIND_AFTER_MS and game.pixel_is(615, 590, 0x00A400, quiet=True):
            game.sleep(SECOND_WIND_SETTLE_MS)
            end = "second wind"
            break
        t = game.now() / 1000
        img = game.grab(game.ox, game.oy, game.ox + w - 1, game.oy + h - 1)
        if section_done(img):
            end = "banner"
            break
        plats, pl = platforms(img), player(img)
        v = speed.update(t, plats, w)
        ground = standing_on(pl, plats)
        if ground is None and last_ground and pl and pl[0] < 70 and -5 <= last_ground[2] - pl[3] <= 55:
            # the player's feet hide the top edge of a short rest of platform: carry the last one along
            dx = round(v * (t - last_ground_t))
            if last_ground[1] - dx >= 80:
                ground = (last_ground[0] - dx, last_ground[1] - dx, last_ground[2])
        elif ground is not None:
            last_ground, last_ground_t = ground, t
        else:
            last_ground = None
        if ground is None or t - last_jump < MIN_GAP_S:
            continue
        if pl[1] >= 160:  # the boost trail shows before the measured speed catches up
            v = max(v, BOOST_SPEED)
        v_plan = max(v, SPEED)
        reason, kind, target = None, "same", None
        if any(FRONT - 20 < p[0] <= PLAYER_X + 70 and p[2] < ground[2] - 60 for p in plats):
            reason, kind = "wall", "wall"
        else:
            action, kind, target = plan(ground, plats, v_plan)
            if action == "jump":
                reason = "target"
            elif hops and orbs_above(img, ground[2]) > 30 and (target := high_jump_lands(ground, plats, v_plan)):
                reason, kind = "orbs", "up"
            elif ground[1] <= PLAYER_X + EDGE_MARGIN and action != "drop":
                reason = "edge"
                ahead = [p for p in plats if p[0] > FRONT and p != ground]
                kind = "long" if ahead and (ahead[0][0] - PLAYER_X) / v_plan > 0.75 else "same"
        if reason:
            log.debug("%s jump: %s %s, %d ms hold, %.0f px/s, on %s to %s", label, reason, kind, HOLD_MS[kind],
                      v, ground, target)
            game.hold(HOLD_MS[kind], 0)
            last_jump = game.now() / 1000
            jumps += 1
    event("Bonus stage section played", where=label, end=end, jumps=jumps)
