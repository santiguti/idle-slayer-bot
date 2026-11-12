"""The main loop, ported from Main() in Idle Runner.au3: fast checks every ~40 ms, slow checks every 5 s."""
import dataclasses
import signal
import threading
from collections.abc import Callable
from datetime import date
from pathlib import Path

from idle_runner.actions import (BIDIMENSIONAL_STAFF, DIMENSIONAL_STAFF, RAGE_PILL, SOUL_COMPASS,
                                 box_on_screen, buy_temp_item, close_all, soul_bonus_active)
from idle_runner.coins import read_coins
from idle_runner.config import Settings
from idle_runner.game import Game
from idle_runner.game_settings import check_game_settings
from idle_runner.log import event, log
from idle_runner.minigames.chest_hunt import chest_hunt
from idle_runner.minions import DAILY_BONUS_MS, mission_ms, send_minions
from idle_runner.minigames.bonus_stage import bonus_stage
from idle_runner.minigames.boss import boss_fight_knight, boss_fight_victor
from idle_runner.minigames.ascending_heights import ascending_heights
from idle_runner.portals import portal_ready, take_portal
from idle_runner.repeater import Repeater
from idle_runner.shop import Shop
from idle_runner.state import load_state, update_state
from idle_runner.tree import Tree
from idle_runner.game import GameUnavailable, WindowGone

EXPECTED_SIZE = (1280, 720)
WINDOW_RETRY_MS = 2000  # how often to look for the game window again after it is gone
BOX_RETRY_MS = 15_000  # buy again this soon after a Random Box stopped a buy
SIX_COIN_TIMEOUT_MS = 120_000  # buy anyway if the counter stays unreadable this long after reading < 6
MINIONS_EVERY_MS = 60 * 60_000  # while no mission end is known (missions sent by hand or before a restart)
MINIONS_MARGIN_MS = 60_000  # look a minute after a mission should end
MAX_CONSECUTIVE_CRASHES = 5  # unexpected errors in a row before giving up (e.g. the game window is gone)
# "MEGA HORDE INCOMING!" (measured 2026-11-02 on 76 hordes recorded 10-29/30). The original's single pixel, the M's
# left edge, also matches the Ascension and Minions panels (open or closing) and other banners ("Time added to Coin
# Value Multiplier!"): 232 of 395 rages on Linux came less than 1 s after a panel routine. The text bobs from 9 px up
# to 25 px down, so the right edge of its "!" (client x 895) gives its height, and the top edges of its letters must
# then all be the outline: 0 false matches in 296 other frames.
HORDE_OUTLINE = 0x140C1C
HORDE_BANG = (903, 255, 903, 325)  # client x 895, y 224-294
HORDE_TOPS = (388, 414, 455, 488, 528, 568, 609, 648, 688, 730, 768, 810, 851, 892)  # on the "!"'s top row
RAGE_HOLDOFF_MS = 5_000  # one rage per horde: its text shows ~1 s, ~20 loops (each tapped R before)


def megahorde_shown(game: Game) -> bool:
    if not game.pixel_is(385, 280, HORDE_OUTLINE, quiet=True):  # the original's check, now only the first
        return False
    bang = game.pixel_search(*HORDE_BANG, HORDE_OUTLINE, quiet=True)  # an open panel matches the first every loop
    return bang is not None and all(game.pixel_is(x, bang[1], HORDE_OUTLINE, quiet=True) for x in HORDE_TOPS)


def install_stop_signals() -> None:
    """Make `kill` (SIGTERM), closing the terminal (SIGHUP) and, on Windows, Ctrl+Break stop the
    bot like Ctrl+C, so the shutdown path still releases every held key."""
    for name in ("SIGTERM", "SIGHUP", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), signal.default_int_handler)


class Runner:
    def __init__(self, game: Game, settings: Settings, jumper: Repeater, state: Path | None = None) -> None:
        self.game = game
        self.s = settings
        self.jumper = jumper
        self.state = state  # state.json: what the bot remembers between starts
        self.shop = Shop(game)
        self.tree = Tree(game, settings.tree_order, state)
        self.tree_due = settings.auto_buy_tree  # once at start: the user may have ascended by hand
        self.minions_due = True  # once at start too: the node may have been bought by hand
        self.settings_due = True  # the in-game settings the bot needs, at the first start of the day
        self.settings_request = threading.Event()  # set by the window's "Check game settings now"
        self.buy_request = threading.Event()  # set by the window's "Buy now" (Heldof's request, 2026-10-29)
        now = game.now()
        self.timer_minions = now
        self.minions_back: list[float] = []  # when the missions the bot sent end
        self.last_slow = now
        self.timer_buy = now
        self.timer_ascend = now
        self.timer_bonus_sample = now
        self.buy_minutes: float = settings.auto_buy_minutes  # $iAutoBuyTempTimer
        self.portal_count = settings.circle_portals_count
        self.last_rage = -RAGE_HOLDOFF_MS  # when the last horde was raged at
        # The original unticks these after one use; with a read-only config they apply once per run.
        self.dimensional_pending = settings.craft_dimensional_staff
        self.bidimensional_pending = settings.craft_bidimensional_staff
        self.paused_reason: str | None = None
        self.unavailable_reason: str | None = None  # last GameUnavailable, until a tick completes
        self.coins_low_since: float | None = None  # when the counter last read under 6 (after an ascension)
        self.retry_buy_at: float | None = None  # set when a Random Box stopped a buy or the shop did not open

    def run(self) -> None:
        g = self.game
        event("Bot started", window=f"{g.size[0]}x{g.size[1]}", **dataclasses.asdict(self.s))
        if g.size != EXPECTED_SIZE:
            log.warning("the game window is %dx%d; it must be 1280x720 or no pixel check will match", *g.size)
            event("Window size mismatch", expected="1280x720", actual=f"{g.size[0]}x{g.size[1]}")
        self.jumper.resume()
        crashes = 0
        try:
            while True:
                try:
                    self.tick()
                    crashes = 0
                    if self.unavailable_reason:
                        event("Resumed")
                        self.unavailable_reason = None
                except WindowGone:
                    event("Game window lost")
                    self.wait_for_window()
                except GameUnavailable as exc:
                    if str(exc) != self.unavailable_reason:  # once per state change, not every tick
                        event("Game unavailable", reason=str(exc))
                        self.unavailable_reason = str(exc)
                    g.sleep(500)
                except Exception:
                    crashes += 1
                    log.exception("tick crashed (%d in a row)", crashes)
                    event("tick_crash", in_a_row=crashes)
                    if crashes >= MAX_CONSECUTIVE_CRASHES:
                        event("Bot stopped after repeated errors")
                        raise
                    g.sleep(5000)
        except KeyboardInterrupt:
            event("Bot stopped")
        finally:
            try:
                self.jumper.stop()
            finally:
                g.release_all()  # even if a second Ctrl+C interrupts the jumper shutdown

    def wait_for_window(self) -> None:
        """After the game window is destroyed (game closed or restarted), look it up by name again."""
        while True:
            self.game.sleep(WINDOW_RETRY_MS)
            try:
                self.game.find_window()
            except GameUnavailable:
                continue
            event("Game window found")
            return

    def tick(self) -> None:
        """One iteration of the original Main() loop."""
        g, s = self.game, self.s
        g.sleep(40)
        size = g.refresh_size()
        if size != EXPECTED_SIZE:
            reason = f"window is {size[0]}x{size[1]}, expected 1280x720"
        elif not g.is_active():
            reason = "game not focused"
        else:
            reason = None
        if reason:
            if reason != self.paused_reason:
                event(f"Paused: {reason}")
                if size != EXPECTED_SIZE:
                    log.warning("paused: %s (no pixel check can match at this size)", reason)
                self.paused_reason = reason
            self.unavailable_reason = None  # the pause explains it; its "Resumed" covers both
            g.sleep(500)
            return
        if self.paused_reason:
            event("Resumed")
            self.paused_reason = None

        # --- fast checks ---
        # Silver box. Its button pulses B78800 -> F8BB00 about once a second; the original's exact CA9700 is
        # one of ~107 shades and never matched in 14 minutes on 2026-10-28. ±16 covers ~40% of each pulse.
        if g.pixel_search(650, 36, 650, 36, 0xCA9700, variation=16, quiet=True):
            event("Silver Box Collected")
            g.click(644, 49)
        if g.now() - self.last_rage >= RAGE_HOLDOFF_MS and megahorde_shown(g):
            self.last_rage = g.now()
            self._routine("rage_when_horde", self.rage_when_horde)
        # A quest can be claimed: the shop button pulses 989898 -> CFCF46. The original matches CBCB4C
        # exactly, one ~7 ms frame at 144 FPS; ±16 covers ~160 ms of each pulse (measured 2026-10-22).
        if g.pixel_search(1130, 610, 1130, 610, 0xCBCB4C, variation=16, quiet=True):
            self._routine("claim_quests", self.shop.claim_quests)
        if soul_bonus_active(g):  # rage during soul bonus
            g.tap("r")
        # Chest hunt. Every coin has the original's two colours 7 px apart (a false start on 2026-10-28), so
        # also ask for the first chest's dark outline at (180, 296), seen in all 62 recorded chest hunts.
        if (g.pixel_is(187, 296, 0xFFBB31, quiet=True) and g.pixel_is(187, 303, 0xF68F37)
                and g.pixel_is(180, 296, 0x151515)):
            self._routine("chest_hunt", lambda: chest_hunt(
                g, s.no_lockpicking, s.perfect_chest_hunt, s.no_reinforced_crystal_saver))

        if s.auto_buy_upgrades:
            self.buy_at_six_coins()

        # --- slow checks, every 5 s ---
        if g.now() - self.last_slow >= 5000:
            self.last_slow = g.now()
            close_all(g)
            asked = self.settings_request.is_set()
            # not in the original, which only listed them
            if (self.settings_due or asked) and self._clear_of_boxes("check_game_settings"):
                self.settings_due = False
                self.settings_request.clear()
                today = date.today().isoformat()
                if not asked and load_state(self.state).get("settings_ok_date") == today:
                    event("Game settings check skipped", reason="checked today")
                else:  # the date is kept only while nothing is wrong or missing: until then, every start checks
                    ok = self._routine("check_game_settings", lambda: check_game_settings(g, self.shop))
                    update_state(self.state, settings_ok_date=today if ok else None)
            if g.pixel_is(660, 254, 0xFFE737) and g.pixel_is(638, 236, 0xFFBB31):  # bonus stage
                self._routine("bonus_stage", lambda: bonus_stage(g, s.skip_bonus_stage))
            if (g.pixel_is(639, 224, 0xFF878A) and g.pixel_is(634, 224, 0xF263BD)
                    and g.pixel_is(644, 224, 0xFFF38F)):  # boss fight
                if g.pixel_is(30, 690, 0x0B0303):
                    self._routine("boss_knight", lambda: boss_fight_knight(g))
                else:
                    self._routine("boss_victor", lambda: boss_fight_victor(g))
            if g.pixel_is(671, 213, 0xC2F4F9) and g.pixel_search(640, 240, 634, 640, 0xFFCC66):  # ascending heights
                self._routine("ascending_heights", lambda: ascending_heights(g))
            if s.circle_portals and portal_ready(g):
                self._routine("circle_portals", lambda: take_portal(g, self.portal_count))
                self.portal_count = self.portal_count % 9 + 1
            if self.buy_request.is_set():  # not in the original: even with auto_buy_upgrades off
                self.buy_request.clear()
                self.timer_buy = g.now()
                self.buy()
            elif s.auto_buy_upgrades and g.now() - self.timer_buy > self.buy_minutes * 60_000:
                self.timer_buy = g.now()
                self.buy_minutes = min(self.buy_minutes * 2, s.auto_buy_minutes)
                self.buy()
            elif self.retry_buy_at is not None and g.now() >= self.retry_buy_at:
                self.buy()
            bonus = None
            if (s.ascend_bonus_sample_minutes
                    and g.now() - self.timer_bonus_sample > s.ascend_bonus_sample_minutes * 60_000
                    and self._clear_of_boxes("ascend_bonus_sample")):
                self.timer_bonus_sample = g.now()
                keep_open = s.auto_ascend_percent if s.auto_ascend and s.auto_ascend_percent else None
                bonus = self._routine("ascend_bonus_sample",
                                      lambda: self.shop.sample_ascend_bonus(keep_open_at=keep_open))
            # Not in the original: also ascend once the bonus reaches auto_ascend_percent (the wiki's rule).
            reached = bool(s.auto_ascend_percent) and bonus is not None and bonus >= s.auto_ascend_percent
            # When the bonus is reached the sample left the panel open for this: no new panel, so no box check.
            if s.auto_ascend and (reached or (g.now() - self.timer_ascend > s.auto_ascend_minutes * 60_000
                                              and self._clear_of_boxes("auto_ascend"))):
                if reached:
                    event("Ascend bonus reached", percent=bonus)
                self.timer_ascend = g.now()
                self.shop.loop_amount = 0  # the original left this at its last value
                ascended = self._routine("auto_ascend", self.shop.auto_ascend)
                self.tree_due = self.tree_due or ascended
                if ascended and s.post_ascend_first_buy_seconds:
                    self.timer_buy = g.now()
                    self.buy_minutes = s.post_ascend_first_buy_seconds / 60
                    event("Post-ascend buy ramp", first_buy_seconds=s.post_ascend_first_buy_seconds)
            if s.auto_buy_tree and self.tree_due and self._clear_of_boxes("buy_tree"):  # not in the original
                self.tree_due = False
                self._routine("buy_tree", self.tree.buy)
                self.minions_due = True  # it may have just bought a minion
            back = any(t <= g.now() for t in self.minions_back)
            hourly = not self.minions_back and g.now() - self.timer_minions > MINIONS_EVERY_MS
            if (self.minions_due or back or hourly) and self._clear_of_boxes("send_minions"):
                self.minions_due = False
                self.timer_minions = g.now()
                self.minions_back = [t for t in self.minions_back if t > g.now()]
                visit = self._routine("send_minions", lambda: send_minions(g))
                for cost in visit.sent:
                    length = mission_ms(cost, s)
                    if length is not None:
                        self.minions_back.append(g.now() + length + MINIONS_MARGIN_MS)
                if visit.bonus:  # every mission out ends 3 hours sooner: some may be over already
                    self.minions_back = [t - DAILY_BONUS_MS for t in self.minions_back]
                    self.minions_due = True
                if visit.box:  # cut short: the rest of the list once the jumper has the box
                    self.minions_due = True

    def buy(self) -> None:
        """AutoUpgrade; if a Random Box stopped it or the shop didn't open, buy again in BOX_RETRY_MS
        (after the jumper got the box and any minigame it started is over: minigames run as routines
        in between). A shop that doesn't open is retried once, then the normal timer takes over: on
        2026-10-24 a stuck panel kept it shut for 55 minutes."""
        self.shop.loop_amount = 0
        retrying = self.retry_buy_at is not None  # tick() leaves it set while it runs the retry
        completed = self._routine("auto_upgrade", self.shop.auto_upgrade)
        again = not completed and (self.shop.opened or not retrying)
        self.retry_buy_at = self.game.now() + BOX_RETRY_MS if again else None

    def buy_at_six_coins(self) -> None:
        """Not in the original (user's rule, 2026-10-22): after an ascension, by the bot or by hand,
        buy as soon as the counter shows 6 coins, the price of the sword's first level. Then the
        post-ascension ramp takes over."""
        g, s = self.game, self.s
        coins = read_coins(g)
        if coins is not None and coins < 6:
            if self.coins_low_since is None:
                self.coins_low_since = g.now()
            return
        if self.coins_low_since is None:
            return
        if coins is None:
            if g.now() - self.coins_low_since < SIX_COIN_TIMEOUT_MS:
                return
            event("Coins reading timed out")
        else:
            event("Coins reached 6", coins=coins)
        self.coins_low_since = None
        self.tree_due = True  # an ascension, maybe by hand: there is SP to spend
        self.buy()
        self.timer_buy = g.now()
        if s.post_ascend_first_buy_seconds:
            self.buy_minutes = s.post_ascend_first_buy_seconds / 60

    def rage_when_horde(self) -> None:
        g, s = self.game, self.s
        soul_bonus = soul_bonus_active(g)
        if soul_bonus:
            event("MegaHorde Rage with SoulBonus")
            if s.craft_rage_pill:
                buy_temp_item(g, RAGE_PILL)
            if s.craft_soul_bonus:
                buy_temp_item(g, SOUL_COMPASS)
        if soul_bonus or not s.disable_rage_without_soul_bonus:
            self.rage()

    def rage(self) -> None:
        g = self.game
        event("MegaHorde Rage")
        if self.dimensional_pending:
            buy_temp_item(g, DIMENSIONAL_STAFF)
            self.dimensional_pending = False
        if self.bidimensional_pending:
            buy_temp_item(g, BIDIMENSIONAL_STAFF)
            self.bidimensional_pending = False
        g.tap("r")

    def _clear_of_boxes(self, routine: str) -> bool:
        """Whether `routine` may open its panel now. Not in the original. A panel hides the run and the jumper
        waits during a routine, so a Random Box floating by is lost (live 2026-11-12 00:36: right after two
        Silver Boxes, the settings check and two minion visits kept panels open for 29 s while a box went by).
        Until the box is gone, the routine waits for a later slow check."""
        if box_on_screen(self.game):
            event("Panel postponed", routine=routine, reason="Random Box")
            return False
        return True

    def _routine[T](self, name: str, fn: Callable[[], T]) -> T:
        """SyncProcess(False) ... SyncProcess(True) around `fn`, with timing logs."""
        with self.jumper.paused(), self.game.routine(name):
            return fn()
