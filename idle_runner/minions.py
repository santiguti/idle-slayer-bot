"""Send minions on missions from the ascension panel's Minions tab. Replaces the original's MinionsCollect.

On the current game version (measured 2026-10-28) every minion has its own button: "Send on Mission (-N SP)",
"On a Mission..." or, once the mission is over, a green "Claim". The SP a mission brings is collected by
ascending (wiki). The original's "claim all /
send all" clicks land on the Daily Bonus banner, and its trigger, yellow at (99, 113), is the Ascension
button's glow (it glows while ascending is "Recommended"), not minions coming back.
"""
import numpy as np

from idle_runner.actions import TAB_SELECTED, open_ascension_tab
from idle_runner.ascend_bonus import _classify, sp_amount
from idle_runner.config import Settings
from idle_runner.game import Game, Point
from idle_runner.game_settings import _bands
from idle_runner.log import event
from idle_runner.shop import SCROLLBAR_TRACK_1254

SEND = (0x54, 0x17, 0x87)           # "Send on Mission (-N SP)"
AWAY = (0x97, 0x5D, 0xCA)           # "On a Mission..."
# "Claim" when a mission is over: the shop's Unlock green (Santi, 2026-10-28; no screenshot of it yet).
CLAIM = (0x11, 0xA6, 0x22)
HEADER_DIGITS = (0xA6, 0x75, 0xFE)  # the header's "N available"
# The buttons' left margin (client x 402-428): each of their rows has the button's colour somewhere in it, clear of
# the text in English and Spanish ("Realizando una Misión ..." starts at client x 428 and crossed the single
# column at 430 used before; 2026-10-28).
BUTTON_LEFT, BUTTON_RIGHT = 410, 436
LIST_TOP, LIST_BOTTOM = 136, 659    # the list between the header and the tab bar (client y 105-628)
BUTTON_HEIGHT = 120                 # a whole button shows 123 px of its colour (client y 222-344)
# With the tree's "The Chosen One" (Santi, 2026-11-03) each row has an orange Prestige button above a shorter one:
# "+N" Divinity Points for resetting that minion's level (the panel's Divinities tab adds them up as "Prestige
# Minions"). Never clicked. The button under it shows 67-68 px of colour, ~15 px below the box (live 00:11).
PRESTIGE = (0xF8, 0x8F, 0x00)
PRESTIGE_BUTTON_HEIGHT = 64
# Each claim floats "N earned / Ascend to claim them" up over the rows above for ~2.4 s (live 2026-11-03): a button
# under it isn't whole, so on 10-30 a send and a claim went unseen.
EARNED_TEXT_MS = 2500
# "241 M available": a suffixed amount. The game wrote 9,482,458 in full (tree header 2026-10-30), so a suffixed one is
# more, far over any mission cost the bot reads (3,000 at most).
SUFFIXED_SP_MIN = 9_482_458
MAX_STEPS = 20                      # clicks and page turns: five minions need up to 10 clicks and 2 turns
# The list's scrollbar at client x 606 (2026-10-28, five minions): track A0A0A0, thumb BFBFBF, client y 111-625.
# With two or three minions there is no scrollbar.
SCROLLBAR_TOP, SCROLLBAR_BOTTOM = (614, 143), (614, 656)
SCROLL_THUMB = 0xBFBFBF
# A page down: the list (523 px) minus a button (123 px) is 400 px, so every button is whole on some page.
PAGE_NOTCHES = 7                    # 350 px, 50 px a notch
LIST_POINTER = (100, 431)           # over the portraits: no control there
# The Daily Bonus banner above the list (live 2026-10-28, client y 108-210): free on PC, one click takes 3 hours
# off every mission running ("3 hours forwarded!", the SP unchanged) and it's gone until the next day. It pulses
# (red C0-FF, green 07-3A) with its blue always 7C.
DAILY_BONUS = (328, 191)            # its middle
DAILY_BONUS_MS = 3 * 60 * 60_000
# Mission minutes by cost in SP, which is fixed per minion (wiki, Minions): White Knight, Dark Wizard, Skeleton,
# Goo Mutant, Stone Golem. The Ninja and the Cyclops cost "50 B" and "100 B", which never read.
MISSION_MINUTES = {10: 180, 150: 390, 1_000: 180, 1_500: 270, 3_000: 1_380}
# Divinities that make missions faster. They add up and shorten the mission: with the first two the White
# Knight takes "under 2 hours" (wiki), 3 h x (1 - 0.35).
SPEEDUPS = {"work_benefits": 0.15, "improved_work_conditions": 0.20, "greeks_blessing": 0.25}


def mission_ms(cost: int, settings: Settings) -> float | None:
    """How long the mission that costs `cost` SP takes, or None for a cost the table doesn't have."""
    minutes = MISSION_MINUTES.get(cost)
    if minutes is None:
        return None
    return minutes * 60_000 * (1 - sum(share for name, share in SPEEDUPS.items() if getattr(settings, name)))


def read_available_sp(game: Game) -> int | None:
    """The unspent SP in the panel's header ("21,048 available"); SUFFIXED_SP_MIN for "241 M"; or None."""
    band = game.grab(28, 59, 638, 88)  # client x 20-629, y 28-57
    mask = (band == HEADER_DIGITS).all(axis=2)
    amount = sp_amount(mask, band)
    return SUFFIXED_SP_MIN if amount is None and suffixed(mask) else amount


def suffixed(mask: np.ndarray) -> bool:
    """Digits, a wide gap (13 px; 3-4 between digits) and a full-height glyph that isn't one: "241 M" (2026-11-03)."""
    columns = np.concatenate(([0], mask.any(axis=0).astype(int), [0]))
    edges = np.flatnonzero(np.diff(columns))
    starts, ends = edges[::2], edges[1::2]
    glyphs = [trim(mask[:, a:b]) for a, b in zip(starts, ends)]
    for i in range(1, len(glyphs)):
        if starts[i] - ends[i - 1] >= 8:
            digits = [_classify(g) for g in glyphs[:i] if g.shape[0] > 6]  # "." and "," are short
            return (bool(digits) and all(d is not None and d.isdigit() for d in digits)
                    and glyphs[i].shape[0] >= 14 and _classify(glyphs[i]) is None)
    return False


def trim(glyph: np.ndarray) -> np.ndarray:
    rows = np.flatnonzero(glyph.any(axis=1))
    return glyph[rows[0]:rows[-1] + 1]


def read_mission_cost(game: Game, top: int) -> int | None:
    """The cost on the send button whose top edge is at `top`: the white line with "(-10 SP)", the button's third
    line in English and its second in Spanish ("Dar Misión (-1,000 SP)", 2026-10-28)."""
    # Client x 415-591: inside the button in both layouts (English 415-613, Spanish 398-597), clear of the reward bar
    # beside it and of the list's scrollbar right of the Spanish one.
    button = game.grab(423, top, 599, top + BUTTON_HEIGHT)
    white = (button == 255).all(axis=2)
    for first, end in _bands(white):
        line, mask = button[first:end], white[first:end]
        columns = mask.any(axis=0)
        x = 0
        while x < len(columns):
            if not columns[x]:
                x += 1
                continue
            start = x
            while x < len(columns) and columns[x]:
                x += 1
            rows = mask[:, start:x].any(axis=1).nonzero()[0]
            if rows[-1] - rows[0] <= 1:  # the "-", 1 px tall: the digits follow
                cost = sp_amount(mask[:, x:], line[:, x:])
                if cost is not None:
                    return cost  # else a 1 px piece of another glyph ("(" has one): the dash may follow
    return None


def buttons(game: Game, color: tuple[int, int, int] = SEND) -> list[tuple[int, int]]:
    """(top edge, height) of the send buttons (or of buttons of `color`) wholly inside the list, from the top:
    123 px of colour, or 67 under a Prestige box."""
    band = game.grab(BUTTON_LEFT, LIST_TOP, BUTTON_RIGHT, LIST_BOTTOM)
    column = (band == color).all(axis=2).any(axis=1)
    prestige = (band == PRESTIGE).all(axis=2).any(axis=1)
    found, y = [], 0
    while y < len(column):
        if column[y]:
            start = y
            while y < len(column) and column[y]:
                y += 1
            height = y - start
            under_prestige = prestige[max(start - 20, 0):start].any()
            if height >= BUTTON_HEIGHT or (height >= PRESTIGE_BUTTON_HEIGHT and under_prestige):
                found.append((LIST_TOP + start, height))
        y += 1
    return found


def send_buttons(game: Game, color: tuple[int, int, int] = SEND) -> list[int]:
    """The top edges of the send buttons (or of buttons of `color`) wholly inside the list, from the top."""
    return [top for top, _ in buttons(game, color)]


def daily_bonus_shown(game: Game) -> bool:
    """The Daily Bonus banner shows: its left margin (client x 25, y 110-205) is all its pulsing magenta."""
    column = game.grab(33, 141, 33, 236).reshape(-1, 3).astype(int)
    return bool(((column[:, 2] == 0x7C) & (column[:, 0] >= 0xBF) & (column[:, 1] <= 0x40)).all())


def take_daily_bonus(game: Game) -> bool:
    """Click the Daily Bonus banner if it shows; True once it's gone."""
    if not daily_bonus_shown(game):
        return False
    game.click(*DAILY_BONUS)
    deadline = game.now() + 2000  # gone within 100 ms live
    while daily_bonus_shown(game):
        if game.now() > deadline:
            event("Minions daily bonus click had no effect")
            game.save_frame("minions-daily-bonus-no-effect")
            return False
        game.sleep(50)
    event("Minions daily bonus taken")
    return True


def thumb(game: Game) -> tuple[Point | None, Point | None]:
    """The scrollbar thumb's ends, or (None, None) without a scrollbar."""
    return (game.pixel_search(*SCROLLBAR_TOP, *SCROLLBAR_BOTTOM, SCROLL_THUMB),
            game.pixel_search(*SCROLLBAR_BOTTOM, *SCROLLBAR_TOP, SCROLL_THUMB))  # bottom-up


def scroll(game: Game, up: bool, notches: int) -> bool:
    """Wheel the list and wait until it stands still; False if it didn't move. Past either end the list
    stretches and springs back for up to 0.45 s (live 2026-10-28), and buttons read meanwhile are moving:
    20 notches up at the top stretched it so far that 7 down 33 ms later never moved the thumb's top."""
    before = thumb(game)
    game.wheel(up=up, notches=notches)
    deadline = game.now() + 2000  # the game sometimes stops drawing for over a second
    while thumb(game) == before:
        if game.now() > deadline:
            return False
        game.sleep(10)
    last, still_since = thumb(game), game.now()
    while game.now() - still_since < 100 and game.now() < deadline + 2000:
        game.sleep(10)
        if (now := thumb(game)) != last:
            last, still_since = now, game.now()
    return True


def minions_shown(game: Game) -> bool:
    """Wait up to 2 s for the Minions tab: its shade and a button of a known colour. The shade fades in (200 ms
    after the click it still hadn't when the tree had just switched tabs, live 2026-10-28 02:43), and alone it
    misled once: it stayed on Minions over the Ascension tab's list after a lost click (19:25)."""
    deadline = game.now() + 2000
    while game.now() <= deadline:
        if (game.pixel_search(332, 676, 332, 676, TAB_SELECTED, variation=6)
                and any(send_buttons(game, color) for color in (SEND, AWAY, CLAIM))):
            return True
        game.sleep(20)
    return False


def send_minions(game: Game) -> tuple[list[int], bool]:
    """Claim the minions back from their missions, then send every minion whose mission the unspent SP
    covers. Claims cost nothing; each send is checked against the header's SP:
    without enough, the game may offer to pay the rest with jewels (the tree did, 2026-10-26). The list
    moves when a minion leaves (the Daily Bonus banner above it changes), so the buttons are found again
    after each send. The list holds two or three whole buttons, so it is read from its top a page at a time
    (five minions on 2026-10-28: a claim cut off by the tab bar was never seen). Last the Daily Bonus, while a
    minion is away: after the sends, so their new missions are shortened too. Returns the costs of the
    missions sent and whether the Daily Bonus was taken (after them: they end 3 hours sooner)."""
    sent: list[int] = []
    if not open_ascension_tab(game):
        game.click(570, 694)  # exit
        return sent, False
    for attempt in range(2):
        if attempt:
            event("Shop click retried", target="minions")
        game.click(332, 680)  # minions tab
        if minions_shown(game):
            break
    else:
        if game.pixel_search(332, 676, 332, 676, TAB_SELECTED, variation=6) is None:
            event("Minions tab not shown")
        else:
            event("Minions buttons unknown")
            game.save_frame("minions-buttons-unknown")
        game.click(570, 694)  # exit
        return sent, False
    game.move(*LIST_POINTER)
    if thumb(game)[0]:
        scroll(game, up=True, notches=10)  # to the top: the list scrolls about 4.5 notches
    noted: set[int | None] = set()  # costs already logged as not sent: pages overlap
    away, bonus = False, False  # a minion on a mission seen; the Daily Bonus taken
    for _ in range(MAX_STEPS):
        claims = buttons(game, CLAIM)
        if claims:
            top, height = claims[0]
            game.click(522, top + height // 2)  # the button's middle
            deadline = game.now() + 2000
            while len(send_buttons(game, CLAIM)) >= len(claims):
                if game.now() > deadline:
                    event("Minion not claimed")
                    game.save_frame("minion-claim-no-effect")
                    game.click(570, 694)  # exit
                    return sent, False
                game.sleep(50)
            event("Minion claimed")
            game.sleep(EARNED_TEXT_MS)
            continue
        available = read_available_sp(game)
        if available is None:
            event("Minions SP not readable")
            game.save_frame("minions-sp-unreadable")
            break
        away = away or bool(send_buttons(game, AWAY))
        heights = dict(buttons(game))
        costs = [(top, read_mission_cost(game, top)) for top in heights]
        affordable = [(top, cost) for top, cost in costs if cost is not None and cost <= available]
        if not affordable:
            for top, cost in costs:
                if cost in noted:
                    continue
                noted.add(cost)
                if cost is None:
                    event("Minion not sent", reason="cost not readable")
                    game.save_frame("minion-cost-unreadable")
                else:
                    event("Minion not sent", reason="not enough SP", cost=cost, available=available)
            # A page down, unless the thumb already reaches the track's bottom end (or there is no scrollbar).
            if not (game.pixel_is(*SCROLLBAR_BOTTOM, SCROLLBAR_TRACK_1254)
                    and scroll(game, up=False, notches=PAGE_NOTCHES)):
                bonus = away and take_daily_bonus(game)
                break
            continue
        top, cost = affordable[0]
        game.click(522, top + heights[top] // 2)  # the button's middle
        deadline = game.now() + 2000
        # It went: the SP dropped by the cost, or ("241 M" doesn't move) the button turned "On a Mission...". A jewel
        # offer for missing SP does neither.
        while read_available_sp(game) != available - cost and top not in send_buttons(game, AWAY):
            if game.now() > deadline:
                event("Minion not sent", reason="no effect", cost=cost)
                game.save_frame("minion-send-no-effect")
                game.click(570, 694)  # exit
                return sent, False
            game.sleep(50)
        event("Minion sent", cost=cost)
        sent.append(cost)
    game.click(570, 694)  # exit
    return sent, bonus
