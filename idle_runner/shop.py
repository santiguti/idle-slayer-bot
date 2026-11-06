"""Shop routines ported from Idle Runner.au3: AutoUpgrade, BuyUpgrade, BuyEquipment, ClaimQuests, AutoAscend."""
import time

import numpy as np

from idle_runner.actions import TAB_SELECTED, box_on_screen, open_ascension_tab
from idle_runner.ascend_bonus import read_ascend_bonus
from idle_runner.game import STUCK_MS, Game, Point
from idle_runner.log import event

SCROLLBAR_GRAY = 0xD6D6D6  # scrollbar track at x = 1260
# The track at x = 1254 is A0A0A0 on the current game version (the thumb is B7B7B7), so the original's
# D6D6D6 test there always said "at the top" after one round of 20 notches (measured 2026-10-22).
SCROLLBAR_TRACK_1254 = 0xA0A0A0
# Shop tabs (measured 2026-10-22): the selected tab's background is darker, and only the Upgrades tab
# has the grey "Buy all available" bar where the Equipment tab has its "Max" button (1180, 636).
BUY_ALL_BAR = 0xA5A5A5             # A1A1A1-A8A8A8
# Its right end, clear of its text in English and Spanish ("Compra todo lo disponible" covers (1180, 636));
# x 1208-1268 is that grey on no other tab (recorded tab bars, 2026-10-28).
BUY_ALL_POINT = (1240, 636)
# The tab bar on y = 700 (measured 2026-10-25, before and after the Ultra Ascension):
#   six tabs:  Equipment 820-889, Upgrades 896-965, Quests 972-1041, Jewels 1048-1117, ⋮ 1124-1192, X 1200-1268
#   five tabs: Equipment 820-904, Upgrades 911-995, Jewels 1002-1086, ⋮ 1093-1177, X 1184-1268
# The five-tab bar shows until quests are unlocked again after an Ultra Ascension. There, the Quests click
# (1000, 690) opens the Jewels shop (outfits bought with jewels).
X_TAB_RED = 0xA61010
# Not in the original (measured 2026-10-22): event quests (new on 2026-10-21) put their rewards at the
# top of the Upgrades list as blue "Quest Reward" rows that can't be bought.
QUEST_REWARD_BLUE = 0x0B6BA1  # their background, at x = 1130
# Their button at x = 1180: grey "Quest Reward" until the event quest's reward is claimed, then a normal
# "Unlock" button (green 11A622 when affordable): the row stays blue but can be bought (2026-10-23).
QUEST_REWARD_GREY = 0x7A7A7A
# The Quests tab's icon: E03C28 at rest (639 frames recorded 2026-10-22, green always 0x3C). While something
# can be claimed it pulses towards ED8C18 (green up to 0xA5) about once a second, selected or not.
QUESTS_ICON = (1000, 690)
# Not in the original (measured 2026-10-27): the free "+2" button beside the Daily Quests header adds two
# Daily Quests until the next reset, then disappears. Solid 379D37 at x = 1188, 32 px tall (466-497 under
# Phantom Fall's event quests); the header around it is 2A1203, claim buttons are 11A622.
EXTRA_DAILIES_GREEN = 0x379D37
EXTRA_DAILIES_HOVER = 0x266E26  # under the pointer: at once after the click, before it goes (live 2026-10-28)
EXTRA_DAILIES_X = 1188
WHEEL_PX = 50  # one wheel notch scrolls a shop list by 50 px
# The ascension panel since the Ultra Ascension node was bought (measured 2026-10-23, client x): Ascend
# 92-307, Ultra Ascend 332-549. The original's confirm click (550, 580) is client (542, 549), inside Ultra
# Ascend whenever the "Are you sure?" dialog isn't up yet or the Ascend click got lost. (598, 581) is
# client (590, 550): "Yes" (493-624) in that dialog, "Close" in "You can't Ascend" (nothing to claim),
# and empty panel (441C06) without a dialog. It is never Ultra Ascend.
ASCEND_CONFIRM = (598, 581)
ASCEND_YES = 0x00A400
CANT_ASCEND_CLOSE = 0xAF0000
ASCEND_ICON = 0xA328B3  # magenta of the dialogs' Ascension icon; Ultra Ascend is cyan and dark blue
FIRST_SEPARATOR_Y = 153  # line above the first Upgrades row when the list is at its top


def daily_quests_day() -> int:
    """The current Daily Quests day. They reset at 00:00 UTC (21:00 in Argentina: the wiki, and the "New in"
    countdown on 2026-10-26). The day starts 10 minutes late here, so a look just before the reset never
    counts for the new day."""
    return int((time.time() - 600) // 86400)


class BoxOnScreen(Exception):
    """A Random Box floats over the run: stop shopping so the jumper can hit it (user's request,
    2026-10-23; the original kept buying and the box flew by)."""


def scroll_to_top(game: Game, x: int, y: int, where: str, pause_ms: float = 0) -> None:
    """Wheel up until the scrollbar's track no longer shows at (x, y) (the thumb covers it at the top)."""
    deadline = game.now() + STUCK_MS
    while True:
        game.wheel(up=True, notches=20)
        game.sleep(pause_ms)
        if not game.pixel_is(x, y, SCROLLBAR_TRACK_1254):
            return
        if game.now() > deadline:
            game.stuck(f"{where}.scroll_top")
            return


def first_row_after_quest_rewards(game: Game) -> int:
    """Scroll the Upgrades list past its "Quest Reward" rows (blue, grey button); return the y of the next row.

    BuyUpgrade only ever buys the top row (y = 170), so those rows stopped it at once. Rows are 96 px
    apart and a notch scrolls 50 px, so this scrolls until the next row's separator is within one
    notch of the list top, then returns the same y the original uses for the top row. Blue rows with a
    buy button are claimed rewards and are bought like any other row.
    """
    def lowest(color: int, x: int) -> Point | None:
        return game.pixel_search(x, 609, x, FIRST_SEPARATOR_Y, color)  # bottom-up

    def rewards_end() -> int | None:
        """The separator under the lowest Quest Reward row (610 if it runs past the list), or None."""
        grey = lowest(QUEST_REWARD_GREY, 1180)
        if grey is None or not game.pixel_is(1130, grey[1], QUEST_REWARD_BLUE):
            return None
        below = game.pixel_search(1180, grey[1], 1180, 609, 0x000000)  # the button's text outline is 140C1C
        return below[1] if below else 610

    end = rewards_end()
    notches = 0
    while end and end > FIRST_SEPARATOR_Y + WHEEL_PX:
        # The lowest row separator always moves when the list does (a notch isn't a multiple of 96 px).
        separator = lowest(0x000000, 1180)
        game.wheel(up=False, notches=1)
        deadline = game.now() + 2000  # the game sometimes stops drawing for over a second
        while lowest(0x000000, 1180) == separator and game.now() <= deadline:
            game.sleep(10)
        if lowest(0x000000, 1180) == separator:
            break  # the list can't scroll any further
        notches += 1
        end = rewards_end()
    if end is None:
        return 170  # no Quest Reward rows: the original's top row
    event("Quest Reward rows skipped", notches=notches)
    return end + (170 - FIRST_SEPARATOR_Y)


class Shop:
    def __init__(self, game: Game) -> None:
        self.game = game
        # $iAutoBuyLoopAmount: caps the BuyUpgrade <-> BuyEquipment rounds at 6. The main loop
        # resets it before each timed buy; nothing else does (known issue kept from the original).
        self.loop_amount = 0
        self.upgrades_bought = 0
        self.equipment_buys = 0
        self.opened = False  # whether the last auto_upgrade got the shop open
        self.dailies_day: int | None = None  # the Daily Quests day whose "+2" was taken or looked for

    def close_if_open(self) -> None:
        """Close the shop if it's open, then wait for it to finish closing.

        The original clicked (1244, 712) blindly. Reproduced on 2026-10-25: a click on the X tab while
        the shop is still closing (the routine before had closed it 23 ms earlier) leaves an empty dark
        panel over the shop that takes every click until Escape (no buys for 55 minutes on 2026-10-23).
        The shop takes about 120 ms to close; the original slept 150 ms.
        """
        g = self.game
        if g.pixel_search(807, 140, 807, 155, 0xFFFFFF):  # the shop's corner, as in open_shop
            g.click(1244, 712)
        g.sleep(300)

    def open_shop(self) -> bool:
        """Click the shop button and wait for the shop's corner; click once more if it doesn't show.

        Not in the original, which checked once, 150 ms after the click. Measured 2026-10-22: the
        shop sometimes appears 110-210 ms after the click, and sometimes a click never reaches the
        game. A second click is safe because the shop is known to be closed by then.
        """
        g = self.game
        g.click(1163, 655)  # open the shop window
        g.sleep(150)
        if g.find_until(807, 140, 807, 155, 0xFFFFFF, timeout_ms=1000):
            return True
        event("Shop click retried", target="shop")
        g.click(1163, 655)
        return g.find_until(807, 140, 807, 155, 0xFFFFFF, timeout_ms=2000) is not None

    def select_tab(self, tab: str, x: int, y: int, sleep_ms: float) -> bool:
        """Click a shop tab and wait until it shows; click once more if it doesn't (see open_shop)."""
        g = self.game
        g.click(x, y)
        g.sleep(sleep_ms)
        if self.tab_shown(tab, timeout_ms=1000):
            return True
        event("Shop click retried", target=tab)
        g.click(x, y)
        if self.tab_shown(tab, timeout_ms=2000):
            return True
        event("Shop tab not shown", tab=tab)
        g.save_frame(f"tab-not-shown-{tab}")
        return False

    def tab_shown(self, tab: str, timeout_ms: float = 2000) -> bool:
        """Wait until `tab` ("armor", "upgrades" or "quests") is the one on screen.

        Not in the original. A tab click can take effect late, like opening the shop, and a click
        meant for one tab then lands on another: "Max" in Equipment is "Buy all available" in
        Upgrades, and a green "Claim" in Quests is a green "Unlock" in Upgrades (this bought the
        Vertical Magnet on 2026-10-22). Requires two matching reads 50 ms apart (the tab fades in).
        x = 820 and 915 are inside Equipment and Upgrades in both tab bars (see X_TAB_RED).
        """
        g = self.game

        def selected(x: int) -> bool:
            return g.pixel_search(x, 700, x, 700, TAB_SELECTED, variation=6) is not None

        def showing() -> bool:
            armor = selected(820)
            upgrades = selected(915)
            buy_all = g.pixel_search(*BUY_ALL_POINT, *BUY_ALL_POINT, BUY_ALL_BAR, variation=4) is not None
            if tab == "armor":
                return armor and not buy_all
            if tab == "upgrades":
                return upgrades and buy_all
            # Quests turns gold instead of darker when something can be claimed, so it is the selected tab
            # when the bar has it and no other tab is selected: not Jewels (1050) or ⋮ (1130) either.
            return self.has_quests_tab() and not (armor or upgrades or buy_all or selected(1050) or selected(1130))

        deadline = g.now() + timeout_ms
        while g.now() <= deadline:
            if showing():
                g.sleep(50)
                if showing():
                    return True
            g.sleep(10)
        return False

    def has_quests_tab(self) -> bool:
        """The tab bar shows and has the Quests tab: the X tab starts at 1200 (six tabs), not 1184."""
        g = self.game
        return g.pixel_is(1210, 700, X_TAB_RED) and not g.pixel_is(1190, 700, X_TAB_RED)

    def row_around(self, y: int) -> tuple[int, int] | None:
        """The Upgrades row whose buy button holds (1180, y): its first and last pixel rows, or None if
        part of it is outside the visible list (y 153-609). Rows are 93 px under a black separator
        (measured: 156-248, 252-344, ...), found going up from y at x = 1180."""
        above = self.game.pixel_search(1180, y, 1180, FIRST_SEPARATOR_Y, 0x000000)  # nearest, going up
        if above is None or above[1] + 93 > 609 or above[1] + 93 < y + 10:  # y + 10: the green check
            return None
        return above[1] + 1, above[1] + 93

    def row_changed(self, top: int, bottom: int, before: np.ndarray) -> bool:
        """Wait until a bought row is gone (the game takes 110-210 ms, longer in a stall), so the next
        check never sees the old row while the click lands on the one that moved up."""
        g = self.game
        deadline = g.now() + 2000
        while g.now() <= deadline:
            if not np.array_equal(g.grab(815, top, 1150, bottom), before):
                return True
            g.sleep(10)
        return False

    def stop_for_box(self) -> None:
        if box_on_screen(self.game):
            raise BoxOnScreen

    def auto_upgrade(self) -> bool:
        """AutoUpgrade. Returns False when it should be retried soon: a Random Box interrupted it (the
        shop is closed again) or the shop didn't open (e.g. a minigame's results screen still covers it)."""
        g = self.game
        event("AutoUpgrade Active")
        self.upgrades_bought = 0
        self.equipment_buys = 0
        self.close_if_open()
        completed = True
        self.opened = self.open_shop()
        if self.opened:
            try:
                self.buy_upgrade()
            except BoxOnScreen:
                event("Shopping stopped for a Random Box")
                g.click(1222, 677)  # close the shop so the player can jump into the box
                completed = False
        else:
            event("AutoUpgrade shop not open")
            g.save_frame("shop-not-open")
            completed = False
        event("AutoUpgrade Done", upgrades=self.upgrades_bought, equipment=self.equipment_buys,
              rounds=self.loop_amount)
        return completed

    def buy_upgrade(self) -> None:
        g = self.game
        if not self.select_tab("upgrades", 927, 683, sleep_ms=150):
            g.click(1222, 677)  # close the shop
            return
        g.move(1254, 172)  # over the scrollbar
        scroll_to_top(g, 1254, 167, "buy_upgrade")
        g.sleep(400)
        # Not in the original: 0.4 s after the wheel the list can still be bouncing back to the top. The first row
        # then looked cut off and was left for a later round (18 of 192 visits, 2026-11-05/06).
        g.find_until(1180, 170, 1180, FIRST_SEPARATOR_Y, 0x000000, timeout_ms=1000)
        bought = False
        y = first_row_after_quest_rewards(g)
        deadline = g.now() + STUCK_MS
        while y + 10 <= 609:
            self.stop_for_box()
            if g.now() > deadline:
                g.stuck("buy_upgrade", y=y)
                break
            row = self.row_around(y)
            if row is None:  # cut off by the list's edge: its icon may be hidden, never buy it
                y += 96
                continue
            top, bottom = row
            # Rows the original never buys (its tooltip: Vertical Magnet and Electric Worms). The
            # original checked y..y + 72 for one of each, in this order; this checks the whole row
            # under the click point, as many times as needed (it bought the magnet on 2026-10-22/23).
            if (g.pixel_search(882, top, 909, bottom, 0xF4B41B)
                    or g.pixel_search(882, top, 909, bottom, 0xE478FF)):
                y += 96
                continue
            if not (g.pixel_is(1180, y + 10, 0x11A622) or g.pixel_is(1180, y + 10, 0x0C7418)):
                break
            bought = True
            self.upgrades_bought += 1
            before = g.grab(815, top, 1150, bottom).copy()
            g.click(1180, y)  # green buy button
            g.sleep(50)
            if not self.row_changed(top, bottom, before):
                event("Upgrade click had no effect", y=y)
                break
        # The original went on to equipment only after buying an upgrade, so right after an ascension
        # (nothing but the sword affordable) it bought nothing. The first round always buys equipment.
        if (bought or self.loop_amount == 0) and self.loop_amount < 6:
            self.loop_amount += 1
            self.buy_equipment()
        else:
            self.finish_visit()

    def buy_equipment(self) -> None:
        g = self.game
        if not self.select_tab("armor", 850, 690, sleep_ms=50):
            g.click(1222, 677)  # close the shop
            return
        self.stop_for_box()
        g.click(1180, 636, clicks=4)  # "max" buy amount
        if g.pixel_is(1257, 340, 0x11AA23):  # no scrollbar: buy the first item (sword)
            g.click(1200, 200, clicks=5)
            self.equipment_buys += 1
        else:
            g.click(1253, 592, clicks=5)  # bottom of the scrollbar
            g.sleep(200)
        deadline = g.now() + STUCK_MS
        while True:
            self.stop_for_box()
            found = g.pixel_search(1160, 590, 1160, 170, 0x11AA23, variation=10)  # bottom to top
            if found is None:
                g.move(1260, 170)
                g.wheel(up=True, notches=1)
                if not g.pixel_is(1260, 168, SCROLLBAR_GRAY):
                    break
                g.sleep(10)
            else:
                g.click(850, 690)  # armor tab (as in the original)
                g.click(*found, clicks=5)
                self.equipment_buys += 1
            if g.now() > deadline:
                g.stuck("buy_equipment")
                break
        self.buy_upgrade()

    def claim_quests(self) -> None:
        g = self.game
        event("Claiming quest")
        self.close_if_open()
        if not self.open_shop():  # not in the original, which clicked on regardless
            event("Claim quests: shop not open")
            g.save_frame("claim-shop-not-open")
            return
        g.click(850, 690)  # armor tab
        g.click(927, 683)  # upgrades tab
        g.sleep(150)
        if not self.has_quests_tab():  # not in the original: (1000, 690) would open the Jewels shop
            event("Claim quests: no Quests tab")
            g.save_frame("claim-no-quests-tab")
            g.click(1244, 712)  # close the shop
            return
        if not self.quests_claimable():  # the shop button's glow isn't only quests (2026-10-23)
            event("Claim quests: nothing to claim")
            g.click(1244, 712)  # close the shop
            return
        try:
            self.claim_in_shop()
        except BoxOnScreen:  # the shop button keeps glowing: the claim runs again later
            event("Shopping stopped for a Random Box")
        g.click(1244, 712)  # close the shop

    def quests_claimable(self, watch_ms: float = 600) -> bool:
        """The Quests tab glows: a reward can be claimed. The glow pulses about once a second and stays above
        green 0x50 for more than half of it (measured 2026-10-22, 10 fps), so 0.6 s of watching always sees
        it; at rest the green is 0x3C."""
        g = self.game
        deadline = g.now() + watch_ms
        while True:
            red, green, _ = (int(c) for c in g.grab(*QUESTS_ICON, *QUESTS_ICON)[0, 0])
            if red >= 0xD0 and green >= 0x50:
                return True
            if g.now() > deadline:
                return False
            g.sleep(30)

    def finish_visit(self) -> None:
        """Close the shop after buying, claiming first if the Quests tab glows: one visit instead of two.
        Once a Daily Quests day it goes through the Quests tab anyway, for the "+2" button."""
        if self.has_quests_tab() and (self.dailies_day != daily_quests_day() or self.quests_claimable()):
            event("Claiming quest")
            self.claim_in_shop()
        self.game.click(1222, 677)  # close the shop

    def claim_in_shop(self) -> None:
        """With the shop open: the Quests tab, then every green claim button in it. Leaves the shop open.
        Raises BoxOnScreen when a Random Box shows up (a silver one was lost to the claim loop on 2026-10-28)."""
        g = self.game
        if not self.select_tab("quests", 1000, 690, sleep_ms=50):
            return
        g.move(1254, 272)
        # The original checks y = 267; while the list bounces past the top, the thumb shrinks and 267
        # shows the track, so it kept wheeling up (blank panel, 2026-10-22). The thumb's top end, at
        # y = 160, stays put.
        scroll_to_top(g, 1254, 160, "claim_quests", pause_ms=20)
        g.sleep(600)
        g.save_frame("claim-quests-start")  # not in the original: shows a claim it can't see (event quests)
        deadline = g.now() + STUCK_MS
        while True:
            self.stop_for_box()
            found = g.pixel_search(1160, 270, 1160, 590, 0x11A622, variation=10)
            if found is None:
                self.take_extra_dailies()
                g.move(1267, 270)
                g.wheel(up=False, notches=1)
                if not g.pixel_is(1267, 658, 0xA0A0A0):  # no gray scrollbar
                    break
                if g.pixel_is(1267, 655, 0xFFFFFF):  # reached the bottom
                    break
                g.sleep(100)
            else:
                event("Quest Claimed")
                g.click(*found)
                # The button stays green a moment: without this wait it was clicked 2-3 times, ~21 ms apart.
                settle = g.now() + 1000
                while g.pixel_search(*found, *found, 0x11A622, variation=10) and g.now() < settle:
                    g.sleep(10)
            if g.now() > deadline:
                g.stuck("claim_quests")
                break
        self.dailies_day = daily_quests_day()
        g.save_frame("claim-quests-end")

    def take_extra_dailies(self) -> None:
        """With the Quests tab showing: click the "+2" beside the Daily Quests header, once a Daily Quests
        day. Not in the original (user's request, 2026-10-28). The click must land on the button: with only
        its bottom showing under the list's top edge, 15 px lower is the first daily quest's Reroll."""
        g = self.game
        found = g.pixel_search(EXTRA_DAILIES_X, 160, EXTRA_DAILIES_X, 620, EXTRA_DAILIES_GREEN, variation=6)
        if found is None or self.dailies_day == daily_quests_day():
            return
        x, y = found[0], found[1] + 15  # the button's middle
        if not g.pixel_search(x, y, x, y, EXTRA_DAILIES_GREEN, variation=6):
            return
        self.dailies_day = daily_quests_day()
        event("Extra daily quests taken")
        g.click(x, y)
        settle = g.now() + 2000
        while any(g.pixel_search(x, y, x, y, c, variation=6) for c in (EXTRA_DAILIES_GREEN, EXTRA_DAILIES_HOVER)):
            if g.now() > settle:
                event("Extra daily quests click had no effect")
                break
            g.sleep(50)
        g.save_frame("extra-daily-quests")

    def sample_ascend_bonus(self, keep_open_at: float | None = None) -> float | None:
        """Open the Ascension tab, read the Ascend button's "+X% CpS bonus" and close the panel. Not in
        the original. Returns the % (0.0 for "+0"), or None when the panel didn't show or can't be read;
        an unreadable one saves a frame, to add its glyphs to idle_runner/bonus_glyphs.py.

        A bonus of at least `keep_open_at` leaves the panel open for auto_ascend: closing it and opening it
        again right away lost the click 4 times of 7 on 2026-10-26 ("Shop click retried", ~2 s each)."""
        g = self.game
        bonus = None
        if not open_ascension_tab(g):
            event("Ascend bonus not shown")
            g.save_frame("ascend-bonus-not-shown")
        elif (bonus := read_ascend_bonus(g)) is None:
            event("Ascend bonus unreadable")
            g.save_frame("ascend-bonus-unreadable")
        else:
            event("Ascend bonus", percent=bonus)
        if bonus is None or keep_open_at is None or bonus < keep_open_at:
            g.click(570, 694)  # close the panel (its X tab, as CollectMinion does)
        return bonus

    def auto_ascend(self) -> bool:
        """Ascend. Returns False when it didn't ascend.

        The original bought right after ascending. The game shows no shop button until the first coins, so
        that buy failed 7 times of 7 on 2026-10-26; Runner.buy_at_six_coins buys as soon as there are 6."""
        g = self.game
        if g.pixel_is(260, 600, 0x58188D):  # the ascension panel is already open
            return self._ascend("panel_open")
        # Known issue kept from the original: it checks y = 480 but clicks y = 600.
        if open_ascension_tab(g):
            return self._ascend("opened_panel")
        event("Ascend skipped", reason="ascend button not found")
        g.save_frame("ascend-not-found")
        return False

    def ascend_dialog(self) -> int | None:
        """Wait up to 2 s for the dialog the Ascend button opens. Returns the colour under ASCEND_CONFIRM:
        ASCEND_YES ("Are you sure?") or CANT_ASCEND_CLOSE ("You can't Ascend"), or None."""
        g = self.game
        deadline = g.now() + 2000
        while True:
            if g.pixel_search(608, 231, 688, 301, ASCEND_ICON):
                for color in (ASCEND_YES, CANT_ASCEND_CLOSE):
                    if g.pixel_is(*ASCEND_CONFIRM, color):
                        return color
            if g.now() > deadline:
                return None
            g.sleep(10)

    def _ascend(self, path: str) -> bool:
        """Click Ascend and confirm; never on the Ultra Ascend button (see ASCEND_CONFIRM)."""
        g = self.game
        g.click(260, 600)  # ascend
        dialog = self.ascend_dialog()  # the original slept 300 ms and clicked (550, 580) regardless
        if dialog is None:
            event("Ascend skipped", reason="no dialog after the Ascend click")
            g.save_frame("ascend-no-dialog")
            g.click(570, 694)  # close the panel (its X tab, as CollectMinion does)
            return False
        g.click(*ASCEND_CONFIRM)  # "Yes", or "Close" when there's nothing to claim
        if dialog == CANT_ASCEND_CLOSE:
            event("Ascend skipped", reason="nothing to claim")
            return False
        deadline = g.now() + 2000  # the game answers in 110-210 ms, longer in a stall
        while g.pixel_is(*ASCEND_CONFIRM, ASCEND_YES) and g.now() <= deadline:
            g.sleep(10)
        if g.pixel_is(*ASCEND_CONFIRM, ASCEND_YES):  # the click got lost; repeating it is safe here
            event("Shop click retried", target="ascend confirm")
            g.click(*ASCEND_CONFIRM)
        g.sleep(300)
        event("Ascended", path=path)
        return True
