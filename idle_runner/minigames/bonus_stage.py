"""Bonus stages 2 and 3, ported from Libraries/BonusStage.au3.

The jump sequences are `cSend(press_ms, post_ms)` pairs copied verbatim. BS2 is table-driven
(its four sections share one shape); BS3 interleaves waits for on-screen markers, so it stays
function-per-section like the original.
"""
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from idle_runner.game import STUCK_MS, Game
from idle_runner.log import event
from idle_runner.minigames.common import slide_until, slider_showing

Moves = tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Bs2Section:
    sync: tuple[int, int, int, int, int]  # find_until(left, top, right, bottom, color) before starting
    sync_sleep: int                       # extra wait after the sync marker shows up
    moves: Moves                          # the jump sequence
    fail_check_before_collect: bool
    collect_hold: tuple[int, int] | None  # cSend() before the collection taps
    collect_taps: int                     # Send("{Up}") + Sleep(500), repeated
    sync_also: tuple[int, int, int] | None = None  # a pixel (x, y, color) the sync also waits for
    cut_stalls: bool = False              # jump at once when the player is stuck (see STILL_AREA)


# The original waits for the first stone block's light edge at the single pixel (220, 465). That
# colour only shows while the block stands still, and the block stopped with its edges at 162-181
# in two runs on 2026-10-23 (204-223 on 2026-10-22), so it timed out. This is the span the original
# itself uses for the same block in section 3.
S1_SYNC = (151, 465, 220, 465, 0xCFBCB8)
# The original waits for the magenta slimes (780, 513) BB26DF. They cover the second of section 2's two opening pits
# only once the tree's "Protect" node is bought (wiki; the bot bought it on 2026-10-28 at 17:14 and every BS2
# before had none, so section 2 never started). The slimes sit 13 px right of the pit's left edge (9 of 9 frames,
# 2026-10-28), so the sync now waits for that edge, (767, 631) turning pit-black 151515, while the first pit, 357 px
# to its left, shows at (508, 631): when the first pit's own edge passes (767, 631), the ground is there.
S2_SYNC = (767, 631, 767, 631, 0x151515)
S2_SYNC_ALSO = (508, 631, 0x151515)
S3_SYNC = (151, 465, 220, 465, 0xCFBCB8)
S4_SYNC = (250, 472, 100, 250, 0x0D2030)
# The run's shop button: the stage is over (bonus_stage waits for it at the end too). A section that runs out of time
# after Second Wind ends the stage with no fail screen (live 2026-11-02 15:46).
RUN_SHOP = (1130, 604, 0x989898)

# Not in the original (measured 2026-11-05, `logs/recordings/2026-11-05-bs2/`). Section 2 has a fixed timer, 29.3 s
# from "Go!" (27.3 s left at its sync), and its jumps take 29.6 s: the player stood 5-7 s against walls waiting for
# the next timed jump and the time ran out at the last wall. A still camera means stuck, so the next jump goes at
# once. Terrain right of the player (client x >= 300), every 4th pixel: the mean change between two looks 50 ms
# apart is >= 2.0 while running (median ~12) and ~0.2 while stuck. Standing among orbs, their spin gives ~2 every
# other look (S3's start, 2026-11-06); 2.5 finds the same walls as 1.5 in the four recorded S2s.
STILL_AREA = (308, 181, 1287, 731)
STILL_CHANGE = 2.5
STUCK_LOOKS = 6  # still for 300 ms: a landing against a step pauses the camera up to 0.25 s (5 of 5 recorded),
#                  a wall until the next jump comes (0.35-2 s, 15 of 15)
STUCK_AFTER_MS = 300  # after a jump's release: a jump in place mustn't count as stuck
# After Second Wind the section restarts with "3, 2, 1, Go!" and the player stands still until a key comes (15 s
# sync timeouts on 2026-11-05; the S3/S4 sync timeouts after a rerun since 11-02 look the same).
NUDGE_AFTER_MS = 500
SYNC_MS = 15_000

# Not in the original (Santi, 2026-11-12: "Estamos matando los duendes con la espada en vez de con el arco"). Once a
# section's orbs are in, "Section Completed Flawlessly!" shows at the top (client x 342-933, y 41-79: 6,314 white
# pixels in all 132 frames of the BS2 recorded on 2026-11-12) until the next section's countdown, and 5-10 s after
# it shows comes the reward: coins and a line of Soul Goblins (12, 48, 48 and 60 a section, wiki). The collection's
# taps, one per 500 ms, hopped over most of them (7 of 48 killed in S2, the sword got those). So once the section's
# jumps are over, while the banner is up: Up every SHOOT_MS, a jump and then arrows while airborne (wiki: "fire arrows
# by jumping again while in the air"), like Victor's shooter. Never before the jumps are over: the terrain goes on
# after the orbs are in, and from the banner on the shooting flew the player up against S2's last wall, as high as
# the section, for 26 s (01:19:31). The banner is told by either end: "Section C" (client x 342-480) has 1,431 white
# pixels and "awlessly!" (x 790-933) 1,682; in the 8,008 frames recorded without it, at most 743 and 35. A "Quest
# Completed!" toast slides in from the right over the banner's middle (01:12:02), never over both ends: read in the
# middle, one look found no banner, the shooting ended and the next section took that banner as its own. So the
# shooting ends only once the banner has been gone REWARD_GONE_MS, and a section only takes a banner after a look
# without one.
REWARD_BAND = (350, 72, 941, 110)   # AutoIt: client (342, 41)-(933, 79)
REWARD_ENDS = ((0, 139), (448, 592))  # columns of the band: "Section C", "awlessly!"
REWARD_WHITE_MIN = 1200
REWARD_GONE_MS = 500
SHOOT_MS = 50
REWARD_MAX_MS = 30_000

S2_MOVES: Moves = (
    (156, 719), (47, 687), (360, 1390), (485, 344), (406, 749), (78, 600), (94, 900), (109, 954),
    (31, 672), (515, 1344), (484, 297), (406, 749), (78, 600), (94, 900), (109, 954), (31, 672),
    (515, 1344), (469, 219), (297, 750), (156, 500), (110, 3000), (360, 2984), (531, 2313),
)

BS2_SECTIONS = (
    Bs2Section(S1_SYNC, 200, (
        (94, 1640), (32, 1218), (94, 600), (109, 1828), (63, 640), (47, 688), (78, 1906),
        (141, 1625), (47, 3187), (47, 734), (47, 750), (78, 1203), (110, 5000),
    ), True, (40, 5000), 17),
    Bs2Section(S2_SYNC, 0, S2_MOVES, True, (350, 1000), 20, S2_SYNC_ALSO, cut_stalls=True),
    Bs2Section(S3_SYNC, 0,
               ((109, 1203), (31, 641), (47, 1578), (47, 2437)) * 3 + ((109, 1203), (31, 641), (47, 5125)),
               True, (900, 200), 20),
    Bs2Section(S4_SYNC, 200, (
        (32, 1375), (641, 690), (41, 1375), (41, 1374), (641, 690), (41, 1373), (41, 2500), (31, 809),
        (41, 1375), (41, 1374), (641, 690), (41, 1373), (41, 1372), (641, 690), (41, 1371),
        (41, 0),  # "extra jump just in case"
    ), False, None, 23),
)

BS2_SB_SECTIONS = (
    Bs2Section(S1_SYNC, 200,
               ((94, 1640), (47, 2072), (187, 688), (31, 672), (31, 1700)) * 2 + ((94, 5000),),
               True, (40, 2500), 19),
    Bs2Section(S2_SYNC, 0, S2_MOVES, True, (350, 1000), 20, S2_SYNC_ALSO, cut_stalls=True),
    Bs2Section(S3_SYNC, 0,
               ((109, 1203), (31, 641), (47, 1200), (1, 3100)) * 3 + ((109, 1203), (31, 641), (47, 5125)),
               True, (900, 200), 20),
    Bs2Section(S4_SYNC, 200, (
        (32, 2800), (31, 809), (41, 1200), (100, 900), (641, 500),
        (31, 850), (41, 770), (641, 400),
        (31, 850), (41, 870), (641, 300),
        (31, 850), (41, 790), (641, 400),
        (31, 850), (41, 840), (641, 300),
        (31, 850), (41, 840), (641, 300),
    ), False, None, 23),
)


def holds(game: Game, moves: Moves) -> None:
    for press_ms, post_ms in moves:
        game.hold(press_ms, post_ms)


class Camera:
    """Tells whether the terrain stopped moving since the last look."""

    def __init__(self, game: Game) -> None:
        self.game = game
        self.last: np.ndarray | None = None

    def still(self) -> bool:
        now = self.game.grab(*STILL_AREA)[::4, ::4].astype(np.int16)
        still = self.last is not None and float(np.abs(now - self.last).mean()) < STILL_CHANGE
        self.last = now
        return still


def reward_shown(game: Game) -> bool:
    """The section's "Section Completed Flawlessly!" banner is up: its orbs are in (see REWARD_BAND)."""
    white = (game.grab(*REWARD_BAND) == 255).all(axis=2)
    return any(int(white[:, left:right].sum()) >= REWARD_WHITE_MIN for left, right in REWARD_ENDS)


class Banner:
    """A section's own reward banner: one only counts after a look without any, as the last section's may still be
    up when this one starts (01:12:02, see REWARD_BAND)."""

    def __init__(self, game: Game) -> None:
        self.game = game
        self.armed = False

    def came(self) -> bool:
        shown = reward_shown(self.game)
        self.armed = self.armed or not shown
        return shown and self.armed


def wait_unless_stuck(game: Game, ms: float) -> bool:
    """Sleep `ms` (after a jump), or less if the player gets stuck; True if cut short."""
    deadline = game.now() + ms
    game.sleep(min(STUCK_AFTER_MS, ms))
    camera, streak = Camera(game), 0
    while (left := deadline - game.now()) > 0:
        streak = streak + 1 if camera.still() else 0
        if streak >= STUCK_LOOKS:
            return True
        game.sleep(min(50, left))
    return False


def holds_unless_stuck(game: Game, moves: Moves, label: str) -> None:
    saved, early = 0.0, 0
    for press_ms, post_ms in moves:
        game.hold(press_ms)
        start = game.now()
        if wait_unless_stuck(game, post_ms):
            early += 1
            saved += post_ms - (game.now() - start)
    event("Bonus stage stuck", where=label, early_jumps=early, saved_ms=round(saved))


def bs2_collect(game: Game, section: Bs2Section, banner: Banner) -> bool:
    """The original's closing jumps: a cSend(), then Send("{Up}") + Sleep(500) each. True as soon as the section's
    reward banner is up before a tap: the taps make way for the shooting."""
    if section.collect_hold:
        game.hold(*section.collect_hold)
    for _ in range(section.collect_taps):
        if banner.came():
            return True
        game.tap("Up")
        game.sleep(500)
    return False


def shoot_through_reward(game: Game, label: str) -> None:
    """Shoot the reward's Soul Goblins with the bow (see REWARD_BAND): Up every SHOOT_MS until the banner has given
    way to the next section's countdown for REWARD_GONE_MS, the stage is over (the run's shop button) or
    REWARD_MAX_MS pass."""
    event("Bonus stage reward", where=label)
    deadline = game.now() + REWARD_MAX_MS
    gone_since: float | None = None
    while game.now() < deadline and not game.pixel_is(*RUN_SHOP, quiet=True):
        if reward_shown(game):
            gone_since = None
        elif gone_since is None:
            gone_since = game.now()
        elif game.now() - gone_since >= REWARD_GONE_MS:
            return
        game.tap("Up")
        game.sleep(SHOOT_MS - 10)  # the tap itself takes 10 ms


def sync(game: Game, section: Bs2Section, label: str, nudge: bool) -> None:
    """Wait for the section's marker; with `nudge`, press Up while the player stands still."""
    if not nudge:
        game.find_until(*section.sync, label=label, also=section.sync_also)  # the original carries on regardless
        return
    camera, still_since = Camera(game), None
    deadline = game.now() + SYNC_MS
    while game.now() < deadline:
        found = game.pixel_search(*section.sync, quiet=True)
        if found and section.sync_also:
            found = game.pixel_search(*section.sync_also[:2], *section.sync_also[:2], section.sync_also[2], quiet=True)
        if found:
            return
        if not camera.still():
            still_since = None
        elif still_since is None:
            still_since = game.now()
        elif game.now() - still_since >= NUDGE_AFTER_MS:
            game.tap("Up")
            event("Bonus stage nudge", where=label)
            still_since = None
        game.sleep(50)
    event("Sync timeout", where=label, timeout_ms=SYNC_MS)
    game.save_frame(f"sync-{label}")


def take_second_wind(game: Game, tag: str) -> bool:
    """BonusStageRetry: click "Second Wind" (a free retry of the section) when the fail screen offers it."""
    if game.pixel_is(615, 590, 0x00A400):
        game.click(560, 600)
        event(f"{tag} Retry")
        game.sleep(1000)
        return True
    return False


def stage_fail(game: Game, n: int) -> bool:
    """BonusStageFail: the fail screen is up; close it."""
    if game.pixel_is(716, 600, 0xAF0000):
        game.click(716, 600)
        event(f"BonusStage{n} Failed")
        return True
    return False


def stage_number(game: Game) -> int:
    """Which bonus stage the start screen ("Swipe to Start") belongs to, read before the swipe.

    Bonus Stage 1 (orb goal 15 in its first section, pink sky) shows while the tree's "Bonus Stage 2" node
    isn't bought, e.g. after an Ultra Ascension; the original only knew 2 and 3. Measured 2026-10-26: the
    dimmed sky at (108, 114) is 1E131F in all 12 recorded BS1 starts and 060519 in all 19 BS2 starts.
    """
    if game.pixel_search(160, 498, 200, 498, 0x16171F) is not None:
        return 3
    return 1 if game.pixel_is(108, 114, 0x1E131F) else 2


def bonus_stage(game: Game, skip: bool) -> int:
    """Play (or skip) the bonus stage on screen; returns its number."""
    event("Start of BonusStage")
    game.sleep(200)
    stage = stage_number(game)
    game.save_frame("bonus-stage-start")
    # The original retried while (775, 448) is white, but that pixel is 141416 with the dialog up on this
    # version (2026-10-22): retry while the green handle still shows instead.
    slide_until(game, "bonus_stage", lambda: not slider_showing(game))
    # Bonus Stage 1 is always skipped, as the original skips every stage but 2 and 3: left to the jumper it
    # never got an orb (its blind jumps fall short of the orb arcs: 0/15 live on 2026-10-26 and 2026-10-28).
    if skip or stage == 1:
        do_nothing(game, stage)
    else:
        game.sleep(3900)
        spirit_boost = game.pixel_is(454, 91, 0xE1E0E2)
        event("BonusStage detected", stage=stage, spirit_boost=spirit_boost)
        if stage == 3:
            run_bs3(game, spirit_boost)
        else:
            run_bs2(game, spirit_boost)
    game.save_frame("bonus-stage-end")
    # The reward run, "Bonus Stage Completed!" and the fade outlast the last section by about 14 s (live 2026-10-28
    # 20:17: every shop and ascension click made meanwhile failed). The shop button's grey shows the run is back.
    game.find_until(1130, 604, 1130, 604, 0x989898, timeout_ms=30_000)
    return stage


def do_nothing(game: Game, n: int) -> None:
    """BonusStageDoNothing: let the timer run out, then close the fail screen."""
    event("Do nothing BonusStage Active")
    deadline = game.now() + 3 * STUCK_MS
    while True:
        game.sleep(200)
        if stage_fail(game, n):
            return
        if game.now() > deadline:
            game.stuck("bonus_stage.do_nothing")
            return


# --- Bonus stage 2 ---

def run_bs2(game: Game, sb: bool) -> None:
    """BonusStage2 / BonusStage2SB.

    Not in the original (user's request, 2026-10-22): when a section fails, take the free "Second
    Wind" and rerun the section, as the original does in Bonus Stage 3. It is offered once per stage;
    after that, the fail screen is closed like the original always did.
    """
    tag = "BonusStage2SB" if sb else "BonusStage2"
    event(tag)
    sections = BS2_SB_SECTIONS if sb else BS2_SECTIONS
    retried = False
    number = 1
    while number <= len(sections):
        # The player waits for a key after Second Wind, and when it reaches a section before the last
        # section's closing taps are over (S2 ends sooner since it cuts its stalls).
        if bs2_section(game, sections[number - 1], f"{tag}-s{number}", nudge=retried or number > 1):
            event(f"{tag} Section {number} Complete")
            number += 1
        elif not retried and take_second_wind(game, tag):
            retried = True
        else:
            if not stage_fail(game, 2):
                event(f"{tag} Over", section=number)  # it ended with no fail screen
            return


def bs2_section(game: Game, section: Bs2Section, label: str, nudge: bool = False) -> bool:
    """Play one section; False if it ended on the fail screen. `nudge`: the player may be waiting for a key."""
    def failed() -> bool:  # the fail screen, or the stage already over
        return game.pixel_is(716, 600, 0xAF0000) or game.pixel_is(*RUN_SHOP)

    sync(game, section, label, nudge)
    game.sleep(section.sync_sleep)
    banner = Banner(game)
    banner.came()  # a look at the start: the last section's banner, if still up, isn't this one's
    if section.cut_stalls:
        holds_unless_stuck(game, section.moves, label)
    else:
        holds(game, section.moves)
    if section.fail_check_before_collect and failed():
        return False
    if bs2_collect(game, section, banner):
        shoot_through_reward(game, label)
        return True
    return not failed()


# --- Bonus stage 3 ---

def bs3_tag(sb: bool) -> str:
    return "BonusStage3SB" if sb else "BonusStage3"


def bs3_fail(game: Game, sb: bool) -> bool:
    """BonusStage3Fail: retry if offered, otherwise detect that the stage is over."""
    tag = bs3_tag(sb)
    if take_second_wind(game, tag):
        return True
    if (game.pixel_is(1130, 604, 0x989898)                             # items icon
            or game.pixel_search(115, 570, 125, 590, 0x09439B)          # boost icon
            or game.pixel_search(115, 570, 125, 590, 0x099B66)):        # wind rush icon
        event(f"{tag} Failed")
        return True
    return False


def wall_jump(game: Game, count: int = 5, sleep_ms: int = 50) -> None:
    for _ in range(count):
        game.hold(30, sleep_ms)


def collect_loot_bs3(game: Game, sb: bool, count: int = 25, stop_early: bool = True) -> bool:
    if bs3_fail(game, sb):
        return False
    for i in range(1, count + 1):
        if stop_early and i > 8:
            if game.find_until(1100, 240, 1100, 440, 0x8D87A2, 480):  # the next section already started
                break
        else:
            game.sleep(500)
        game.hold(0, 0)
    return not bs3_fail(game, sb)


def bs3_section1(game: Game, sb: bool) -> bool:
    game.find_until(520, 200, 580, 250, 0xFFFFFF, label=f"{bs3_tag(sb)}-s1-1")
    game.sleep(360)
    holds(game, ((140, 530), (70, 640), (80, 740), (150, 765), (65, 625), (65, 500)))
    game.find_until(540, 335, 555, 360, 0xFFFFFF, 700, label=f"{bs3_tag(sb)}-s1-2")
    holds(game, ((150, 750), (200, 200)))
    game.find_until(390, 230, 410, 250, 0xFFFFFF, 3500, label=f"{bs3_tag(sb)}-s1-3")
    holds(game, ((130, 545), (70, 620), (80, 400)))
    game.find_until(500, 200, 515, 250, 0xFFFFFF, 1500, label=f"{bs3_tag(sb)}-s1-4")
    holds(game, ((150, 755), (65, 625), (65, 500)))
    game.find_until(540, 335, 555, 360, 0xFFFFFF, 700, label=f"{bs3_tag(sb)}-s1-5")
    holds(game, ((150, 740), (200, 1490), (110, 580), (65, 640), (80, 740), (150, 765), (130, 560), (70, 650)))
    game.sleep(800)
    if not collect_loot_bs3(game, sb, 21):
        return False
    event(f"{bs3_tag(sb)} Section 1 Complete")
    return True


def bs3_section2(game: Game, sb: bool) -> bool:
    game.find_until(306, 200, 309, 275, 0xFFFFFF, label=f"{bs3_tag(sb)}-s2-1")
    for _ in range(2):
        holds(game, ((80, 440), (95, 660), (105, 500)))
        game.find_until(475, 445, 482, 475, 0xFFFFFF, 1000, label=f"{bs3_tag(sb)}-s2-2")
        holds(game, ((79, 601), (63, 980), (82, 440), (95, 660), (48, 750)))
        game.find_until(515, 265, 522, 285, 0xFFFFFF, 1200, label=f"{bs3_tag(sb)}-s2-3")
        game.hold(63, 500)
        wall_jump(game, 1)
        game.sleep(80)
        wall_jump(game, 1)
        game.sleep(300)
        wall_jump(game, 4)
        game.find_until(306, 200, 309, 275, 0xFFFFFF, 1000, label=f"{bs3_tag(sb)}-s2-4")
    holds(game, ((80, 440), (95, 660)))
    if not collect_loot_bs3(game, sb):
        return False
    event(f"{bs3_tag(sb)} Section 2 Complete")
    return True


def bs3_section3(game: Game, sb: bool) -> bool:
    upper_way = False
    game.find_until(280, 385, 330, 435, 0xFFFFFF, label=f"{bs3_tag(sb)}-s3-1")
    game.sleep(600)
    for _ in range(2):
        if upper_way:
            wall_jump(game)
            upper_way = False
        else:
            game.hold(120, 100)
            game.find_until(205, 395, 215, 410, 0xFFFFFF, 780, label=f"{bs3_tag(sb)}-s3-2")
            game.hold(95, 225)
            wall_jump(game)
        game.sleep(2000)
        game.hold(300, 500)
        wall_jump(game)
        game.find_until(205, 395, 215, 410, 0xFFFFFF, 900, label=f"{bs3_tag(sb)}-s3-3")
        # The original wraps the rest in `If $iX < 3`, which is always true for its 2 iterations.
        game.hold(95, 250)
        wall_jump(game, 1, 715)
        wall_jump(game, 6)
        landed = game.find_until(300, 415, 330, 435, 0xFFFFFF, 1000 if sb else 2500, label=f"{bs3_tag(sb)}-s3-4")
        if landed is None:  # a timeout here means "take the upper way", so it's logged too
            upper_way = True
        else:
            game.sleep(2500)
        game.sleep(150)
    if not collect_loot_bs3(game, sb):
        return False
    event(f"{bs3_tag(sb)} Section 3 Complete")
    return True


def bs3_section4(game: Game, sb: bool) -> bool:
    game.find_until(330, 170, 380, 195, 0xFFFFFF, label=f"{bs3_tag(sb)}-s4-1")
    if not sb:
        for _ in range(5):
            holds(game, ((300, 600), (300, 420), (35, 748), (35, 540), (35, 1160)))
    else:
        for _ in range(14):
            game.hold(110, 1180)
        game.hold(300, 300)
    if not collect_loot_bs3(game, sb, 25, stop_early=False):
        return False
    event(f"{bs3_tag(sb)} Section 4 Complete")
    return True


BS3_SECTIONS: tuple[Callable[[Game, bool], bool], ...] = (bs3_section1, bs3_section2, bs3_section3, bs3_section4)


def run_bs3(game: Game, sb: bool, sections: tuple[Callable[[Game, bool], bool], ...] = BS3_SECTIONS) -> None:
    """BonusStage3 / BonusStage3SB.

    The original recurses with `$iCurrentSection + 4` when a section fails, which allows one
    retry per stage (it reruns the failed section) and stops at the second failure.
    """
    event(bs3_tag(sb))
    retried = False
    index = 0
    while index < len(sections):
        if sections[index](game, sb):
            index += 1
        elif not retried:
            retried = True
            event("BonusStage3 section rerun", stage=bs3_tag(sb), section=index + 1)
        else:
            return
