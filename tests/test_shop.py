from pathlib import Path

import pytest

from idle_runner.actions import open_ascension_tab
from idle_runner import shop as shop_module
from idle_runner.shop import QUEST_REWARD_BLUE, BoxOnScreen, Shop, first_row_after_quest_rewards, scroll_to_top
from tests.fakes import OFFSET, read_png


def client_click(x: int, y: int) -> tuple:
    """The FakeBackend action recorded for a click at AutoIt (x, y)."""
    return ("click", x - OFFSET[0], y - OFFSET[1])


def show_tab(fake, tab: str) -> None:
    """Paint the shop's six-tab bar as measured on 2026-10-22/25: the X tab's red (1200-1268), the selected
    tab darker, and only the Upgrades tab has the grey "Buy all available" bar (its right end at
    (1240, 636)). "quests" paints no buying tab: the blank fake has no selected tab elsewhere."""
    fake.paint(1210, 700, 0xA61010)
    if tab == "upgrades":
        fake.paint(915, 700, 0x5A251A)
        fake.paint(1240, 636, 0xA8A8A8)
    elif tab == "armor":
        fake.paint(820, 700, 0x5E261B)
        fake.paint(1240, 636, 0x898989)


def paint_tab_bar(fake, name: str) -> None:
    """A tab bar recorded live (tests/fixtures/shop_tabs: client x 780-1279, y 600-719, so it holds the
    "Buy all" / "Max" pixel too). "6-..." has all six tabs; "5-..." is right after an Ultra Ascension,
    without the Quests tab, where every tab is wider. The rest of the name is the tab shown."""
    fake.paint(807, 145, 0xFFFFFF)  # the shop is open
    fake.frame[600:720, 780:1280] = read_png(Path(__file__).parent / "fixtures" / "shop_tabs" / f"{name}.png")


@pytest.mark.parametrize("name, shown", [
    ("6-armor", "armor"), ("6-upgrades", "upgrades"), ("6-quests", "quests"), ("6-quests-gold", "quests"),
    ("5-upgrades", "upgrades"), ("5-jewels", None),
    # The game in Spanish (2026-10-28): "Compra todo lo disponible" is wider and covered (1180, 636) with text.
    ("es-armor", "armor"), ("es-upgrades", "upgrades"), ("es-quests", "quests")])
def test_tab_shown_on_recorded_tab_bars(game, fake, name: str, shown: str | None) -> None:
    paint_tab_bar(fake, name)
    shop = Shop(game)

    showing = [tab for tab in ("armor", "upgrades", "quests") if shop.tab_shown(tab, timeout_ms=100)]
    assert showing == ([shown] if shown else [])


@pytest.mark.parametrize("x", [1050, 1130])  # Jewels, "⋮"
def test_quests_is_not_shown_while_another_non_buying_tab_is_selected(game, fake, x: int) -> None:
    paint_tab_bar(fake, "6-quests")
    fake.paint(972, 700, 0x883424, w=18)  # Quests no longer selected...
    fake.paint(x, 700, 0x5A251A)          # ...this tab is

    assert not Shop(game).tab_shown("quests", timeout_ms=100)


def test_claim_quests_never_clicks_where_quests_would_be_without_a_quests_tab(game, fake, event_names) -> None:
    paint_tab_bar(fake, "5-upgrades")  # (1000, 690) is the Jewels shop here (outfits bought with jewels)
    Shop(game).claim_quests()

    assert (1000, 690) not in fake.clicks()
    assert "Claim quests: no Quests tab" in event_names()
    assert fake.clicks()[-1] == (1244, 712)


ROW_ICONS = {"vm": 0xF4B41B, "svm": 0xE478FF}  # Vertical Magnet / Special Vertical Magnet icon colours


def paint_rows(fake, kinds: list, first_separator: int = 153, icon_rows: tuple[int, int] = (40, 50)) -> None:
    """Upgrades rows as measured on 2026-10-22: a black separator every 96 px (the first at y = 153 at
    the list's top), background 454545, an icon colour in x 885-905 for excluded rows, and the buy
    button at x 1160-1199, green for "buy", "vm" and "svm" rows, red for "red". Only y 153-609 shows.
    Each row also gets its own text colour (like its name in the game); a kind can be (kind, id)."""
    def band(x: int, y0: int, y1: int, w: int, color: int) -> None:
        y0, y1 = max(y0, 153), min(y1, 609)
        if y0 <= y1:
            fake.paint(x, y0, color, w=w, h=y1 - y0 + 1)

    band(800, 153, 609, 472, 0x454545)
    for i, item in enumerate(kinds):
        kind, ident = item if isinstance(item, tuple) else (item, i)
        top = first_separator + 96 * i
        band(800, top, top + 2, 472, 0x000000)
        band(950, top + 30, top + 40, 40, 0x203040 + 0x10 * ident)  # the row's own "name"
        band(1160, top + 3, top + 95, 40, 0xA91111 if kind == "red" else 0x11A622)
        if kind in ROW_ICONS:
            band(885, top + icon_rows[0], top + icon_rows[1], 20, ROW_ICONS[kind])
    band(800, first_separator + 96 * len(kinds), first_separator + 96 * len(kinds) + 2, 472, 0x000000)


def buying_removes_rows(fake, kinds: list[str], first_separator: int = 153) -> list[str]:
    """Each click on a row's button buys it: the row disappears and the rows below move up."""
    rows = [(kind, i) for i, kind in enumerate(kinds)]
    paint_rows(fake, rows, first_separator)

    def on_action(action: tuple) -> None:
        if action[0] != "click":
            return
        x, y = action[1] + OFFSET[0], action[2] + OFFSET[1]
        index = (y - first_separator) // 96
        if 1160 <= x <= 1199 and 0 <= index < len(rows) and rows[index][0] != "red":
            del rows[index]
            paint_rows(fake, rows, first_separator)

    fake.on_action = on_action
    return rows


def test_buy_upgrade_clicks_green_rows_until_none_is_left(game, fake) -> None:
    show_tab(fake, "upgrades")
    buying_removes_rows(fake, ["buy", "buy", "buy", "red"])
    shop = Shop(game)
    shop.loop_amount = 6  # no equipment round: the shop closes right away
    shop.buy_upgrade()

    assert fake.clicks().count((1180, 170)) == 3
    assert fake.clicks()[-1] == (1222, 677)
    assert shop.upgrades_bought == 3


def test_buy_upgrade_skips_the_excluded_upgrades(game, fake) -> None:
    show_tab(fake, "upgrades")
    buying_removes_rows(fake, ["vm", "buy", "red"])
    shop = Shop(game)
    shop.loop_amount = 6
    shop.buy_upgrade()

    assert fake.clicks().count((1180, 266)) == 1
    assert (1180, 170) not in fake.clicks()


def test_auto_upgrade_logs_when_the_shop_does_not_open(game, fake, event_names) -> None:
    completed = Shop(game).auto_upgrade()

    assert completed is False  # the caller retries soon

    assert fake.clicks() == [(1163, 655), (1163, 655)]  # the second: a lost click is retried once
    assert "AutoUpgrade shop not open" in event_names()
    assert "AutoUpgrade Done" in event_names()


def test_stuck_scrollbar_is_reported_instead_of_looping_forever(game, fake, events) -> None:
    show_tab(fake, "upgrades")
    fake.paint(1254, 167, 0xA0A0A0)  # the scrollbar's track, at its top, never goes away
    shop = Shop(game)
    shop.loop_amount = 6
    shop.buy_upgrade()

    assert any(r["event"] == "stuck" and r["where"] == "buy_upgrade.scroll_top" for r in events())


def test_claim_quests_clicks_green_claim_buttons(game, fake, event_names) -> None:
    fake.paint(807, 145, 0xFFFFFF)  # the shop is open
    show_tab(fake, "quests")
    fake.paint(1000, 690, 0xED8C18)  # the Quests tab glows: something to claim
    fake.paint(1160, 300, 0x11A622)
    fake.on_action = lambda a: fake.paint(1160, 300, 0) if a == client_click(1160, 300) else None
    Shop(game).claim_quests()

    assert (1160, 300) in fake.clicks()
    assert event_names().count("Quest Claimed") == 1
    assert fake.clicks()[-1] == (1244, 712)


def ascend_dialog_on_click(fake, color: int) -> None:
    """Clicking Ascend (260, 600) opens a dialog, as measured on 2026-10-23: "Are you sure?" with Yes
    (00A400) under (598, 581), or "You can't Ascend" with its Close (AF0000) there. Both show the magenta
    Ascension icon. Clicking (598, 581) closes the dialog, leaving the empty panel (441C06)."""
    def act(action: tuple) -> None:
        if action == client_click(260, 600):
            fake.paint(598, 581, color)
            fake.paint(648, 271, 0xA328B3)
        elif action == client_click(598, 581):
            fake.paint(598, 581, 0x441C06)
            fake.paint(648, 271, 0)
    fake.on_action = act


def in_ultra_ascend(x: int, y: int) -> bool:
    """The Ultra Ascend button (client x 332-549, y 435-597, measured 2026-10-23), in AutoIt coordinates."""
    return 332 + 8 <= x <= 549 + 8 and 435 + 31 <= y <= 597 + 31


def test_auto_ascend_when_the_panel_is_already_open(game, fake, event_names) -> None:
    fake.paint(260, 600, 0x58188D)
    ascend_dialog_on_click(fake, 0x00A400)

    assert Shop(game).auto_ascend() is True
    # No shop right after: its button only shows with the first coins, so that buy failed 7 of 7 times on
    # 2026-10-26 ("AutoUpgrade shop not open"); the six-coin buy (Runner.buy_at_six_coins) makes it.
    assert fake.clicks() == [(260, 600), (598, 581)]
    assert "Ascended" in event_names() and "AutoUpgrade Active" not in event_names()


def test_auto_ascend_never_clicks_ultra_ascend_when_no_dialog_shows(game, fake, events) -> None:
    fake.paint(260, 480, 0x58188D)  # the Ascend button is there, but its click gets lost

    assert Shop(game).auto_ascend() is False
    assert not [c for c in fake.clicks() if in_ultra_ascend(*c)]
    assert (550, 580) not in fake.clicks()  # the original's confirm click: inside Ultra Ascend
    assert fake.clicks()[-1] == (570, 694)  # closes the panel
    assert [e.get("reason") for e in events() if e["event"] == "Ascend skipped"] == ["no dialog after the Ascend click"]


def test_auto_ascend_closes_the_cant_ascend_dialog(game, fake, events) -> None:
    fake.paint(260, 480, 0x58188D)
    ascend_dialog_on_click(fake, 0xAF0000)

    assert Shop(game).auto_ascend() is False
    assert fake.clicks()[-1] == (598, 581)
    assert events()[-1]["event"] == "Ascend skipped" and events()[-1]["reason"] == "nothing to claim"


def test_auto_ascend_repeats_a_lost_confirm_click(game, fake, event_names) -> None:
    fake.paint(260, 480, 0x58188D)
    ascend_dialog_on_click(fake, 0x00A400)
    dialog = fake.on_action
    lost: list[tuple] = []

    def lose_the_first_confirm(action: tuple) -> None:
        if action == client_click(598, 581) and not lost:
            lost.append(action)  # the game never sees it
        elif dialog:
            dialog(action)
    fake.on_action = lose_the_first_confirm

    assert Shop(game).auto_ascend() is True
    assert fake.clicks().count((598, 581)) == 2
    assert "Shop click retried" in event_names()


def test_auto_ascend_logs_and_saves_a_frame_when_the_button_is_missing(game, fake, event_names) -> None:
    assert Shop(game).auto_ascend() is False
    assert fake.clicks() == [(95, 90), (93, 680), (95, 90), (93, 680)]  # the open is retried once
    assert "Ascend skipped" in event_names()
    assert "frame" in event_names()


def test_claim_quests_saves_frames_of_what_it_saw(game, fake, events) -> None:
    fake.paint(807, 145, 0xFFFFFF)  # the shop is open; the claim isn't visible (an event quest)
    show_tab(fake, "quests")
    fake.paint(1000, 690, 0xED8C18)  # the Quests tab glows: something to claim
    Shop(game).claim_quests()

    labels = [r["label"] for r in events() if r["event"] == "frame"]
    assert labels == ["claim-quests-start", "claim-quests-end"]


def paint_upgrades(fake, quest_rewards: int, offset: int, buyable: bool = True, reward_button: int = 0x7A7A7A) -> None:
    """The Upgrades list scrolled down `offset` px, as measured on 2026-10-22: separators every 96 px
    (the first at y = 153 when the list is at its top), `quest_rewards` blue event rows with a grey
    "Quest Reward" button (green "Unlock" once the reward is claimed, 2026-10-23), then rows with a green
    buy button (red when unaffordable)."""
    def band(x: int, y0: int, y1: int, w: int, color: int) -> None:
        y0, y1 = max(y0, 153), min(y1, 609)  # the visible list
        if y0 <= y1:
            fake.paint(x, y0, color, w=w, h=y1 - y0 + 1)

    band(800, 153, 609, 472, 0x454545)
    for i in range(quest_rewards + 6):
        top = 153 + 96 * i - offset
        reward = i < quest_rewards
        band(800, top, top + 2, 472, 0x000000)
        band(1100, top + 3, top + 95, 50, QUEST_REWARD_BLUE if reward else 0x454545)
        button = reward_button if reward else 0x11A622 if buyable else 0xA91111
        band(1160, top + 3, top + 95, 40, button)


def test_buy_upgrade_scrolls_past_the_event_quest_reward_rows(game, fake) -> None:
    show_tab(fake, "upgrades")
    state = {"offset": 0, "buyable": True}

    def scroll_or_buy(action: tuple) -> None:
        if action == ("button", 5, True):  # wheel down
            state["offset"] += 50
        elif action == ("button", 4, True):  # wheel up
            state["offset"] = max(0, state["offset"] - 50)
        elif action == client_click(1180, 192):
            state["buyable"] = False
        else:
            return
        paint_upgrades(fake, 7, state["offset"], state["buyable"])

    paint_upgrades(fake, 7, 0)
    fake.on_action = scroll_or_buy
    shop = Shop(game)
    shop.loop_amount = 6
    shop.buy_upgrade()

    # 7 rows of 96 px: 13 notches of 50 px leave the first buyable row's separator at 153 + 672 - 650 = 175
    assert state["offset"] == 650
    assert fake.clicks().count((1180, 192)) == 1 and shop.upgrades_bought == 1


def test_buy_upgrade_uses_the_visible_row_when_the_list_cannot_scroll_further(game, fake) -> None:
    show_tab(fake, "upgrades")
    paint_upgrades(fake, 1, 0)  # the wheel changes nothing: the list is already at its end
    fake.on_action = lambda a: paint_upgrades(fake, 1, 0, buyable=False) if a == client_click(1180, 266) else None
    shop = Shop(game)
    shop.loop_amount = 6
    shop.buy_upgrade()

    assert fake.clicks().count((1180, 266)) == 1


def open_shop_late(fake, delay_ms: float) -> None:
    """The shop's corner turns white `delay_ms` after the click on the shop button (seen live: 110-210 ms)."""
    opened_at: list[float] = []
    fake.on_action = lambda a: opened_at.append(fake.t + delay_ms) if a == client_click(1163, 655) else None
    real_grab = fake.grab

    def grab(x: int, y: int, w: int, h: int):
        if opened_at and fake.t >= opened_at[0]:
            fake.paint(807, 140, 0xFFFFFF, h=16)
        return real_grab(x, y, w, h)

    fake.grab = grab


def test_auto_upgrade_waits_for_a_slow_shop(game, fake, event_names, monkeypatch) -> None:
    open_shop_late(fake, 300)
    shop = Shop(game)
    bought = []
    monkeypatch.setattr(shop, "buy_upgrade", lambda: bought.append(True))
    shop.auto_upgrade()

    assert bought and "AutoUpgrade shop not open" not in event_names()


def test_claim_quests_waits_for_a_slow_shop_before_clicking_tabs(game, fake) -> None:
    open_shop_late(fake, 300)
    opening = fake.on_action
    shop_open_at_first_tab = []

    def on_action(action: tuple) -> None:
        opening(action)
        if action == client_click(850, 690):  # armor tab, the first tab click
            shop_open_at_first_tab.append(game.pixel_is(807, 145, 0xFFFFFF))

    fake.on_action = on_action
    Shop(game).claim_quests()

    assert shop_open_at_first_tab == [True]


def test_claim_quests_stops_when_the_shop_never_opens(game, fake, event_names) -> None:
    Shop(game).claim_quests()

    assert fake.clicks() == [(1163, 655), (1163, 655)]  # the second: a lost click is retried once
    assert "Claim quests: shop not open" in event_names()


def test_scroll_to_top_wheels_until_the_thumb_covers_the_top(game, fake) -> None:
    fake.paint(1254, 167, 0xA0A0A0)  # track: the list isn't at its top (the original expected D6D6D6)
    notches = []

    def thumb_reaches_the_top(action: tuple) -> None:
        if action == ("button", 4, True):
            notches.append(1)
            if len(notches) == 45:
                fake.paint(1254, 167, 0xB7B7B7)  # thumb

    fake.on_action = thumb_reaches_the_top
    scroll_to_top(game, 1254, 167, "test")

    assert len(notches) == 60  # three rounds of 20: a long list needs more than one


def test_buy_equipment_does_not_click_max_while_the_upgrades_tab_shows(game, fake, event_names) -> None:
    show_tab(fake, "upgrades")  # the click on the armor tab hasn't taken effect
    shop = Shop(game)
    shop.loop_amount = 6
    shop.buy_equipment()

    assert (1180, 636) not in fake.clicks()  # on the Upgrades tab that is "Buy all available"
    assert "Shop tab not shown" in event_names()


def test_buy_upgrade_does_not_click_while_another_tab_shows(game, fake) -> None:
    show_tab(fake, "armor")
    fake.paint(1180, 180, 0x11A622)
    shop = Shop(game)
    shop.loop_amount = 6
    shop.buy_upgrade()

    assert (1180, 170) not in fake.clicks()


def test_claim_quests_never_clicks_green_on_a_buying_tab(game, fake, event_names) -> None:
    fake.paint(807, 145, 0xFFFFFF)  # the shop is open...
    show_tab(fake, "upgrades")      # ...but still on Upgrades: its green buttons buy things
    fake.paint(1000, 690, 0xED8C18)  # the Quests tab glows: something to claim
    fake.paint(1160, 300, 0x11A622)
    Shop(game).claim_quests()

    assert (1160, 300) not in fake.clicks()
    assert "Shop tab not shown" in event_names()


def test_buy_upgrade_skips_excluded_rows_in_any_order(game, fake) -> None:
    show_tab(fake, "upgrades")
    buying_removes_rows(fake, ["svm", "vm", "buy", "red"])  # the original checks the VM colour first
    shop = Shop(game)
    shop.loop_amount = 6
    shop.buy_upgrade()

    assert fake.clicks().count((1180, 362)) == 1
    assert (1180, 170) not in fake.clicks() and (1180, 266) not in fake.clicks()


def test_selected_tab_shades_measured_live_are_recognised(game, fake) -> None:
    shop = Shop(game)
    fake.paint(1180, 636, 0xFFFFFF)  # Equipment's "Max" button
    for shade, expected in ((0x5A251A, True), (0x5E261B, True), (0x62271C, True), (0x6A281C, False), (0x8E3625, False)):
        fake.paint(820, 700, shade)
        assert shop.tab_shown("armor") is expected, hex(shade)


def test_buy_upgrade_runs_one_equipment_round_even_when_no_upgrade_is_affordable(game, fake) -> None:
    show_tab(fake, "upgrades")  # no green upgrade: right after an ascension only equipment is affordable

    def switch_to_armor(action: tuple) -> None:
        if action == client_click(850, 690):
            fake.paint(897, 700, 0x883424)  # upgrades tab no longer selected
            show_tab(fake, "armor")

    fake.on_action = switch_to_armor
    Shop(game).buy_upgrade()

    assert (1180, 636) in fake.clicks()  # the equipment round ran ("max" buy amount)


def ignore_first_click_at(fake, x: int, y: int, then) -> None:
    """The first click at AutoIt (x, y) doesn't reach the game (seen live on 2026-10-22); `then` runs on the next."""
    seen = []

    def on_action(action: tuple) -> None:
        if action == client_click(x, y):
            seen.append(1)
            if len(seen) == 2:
                then()

    fake.on_action = on_action


def test_routines_click_the_shop_x_only_while_the_shop_is_open(game, fake) -> None:
    # Reproduced 2026-10-25: a click on the X tab while the shop is still closing (the routine before had
    # closed it 23 ms earlier) leaves an empty dark panel over the shop that takes every click until Escape.
    Shop(game).auto_upgrade()
    Shop(game).claim_quests()

    assert (1244, 712) not in fake.clicks()


def test_closing_a_shop_left_open_waits_for_it_before_opening_it_again(game, fake) -> None:
    fake.paint(807, 145, 0xFFFFFF)  # left open
    first_click_at: dict[tuple, float] = {}
    fake.on_action = lambda a: first_click_at.setdefault(a, fake.t)
    Shop(game).claim_quests()

    assert first_click_at[client_click(1163, 655)] - first_click_at[client_click(1244, 712)] >= 300  # closes in ~120 ms


def test_open_ascension_tab_clicks_again_when_the_panel_does_not_open(game, fake, event_names) -> None:
    # Seen live on 2026-10-25: the click that reopened the panel 21 ms after the bonus sample closed it.
    ignore_first_click_at(fake, 95, 90, lambda: fake.paint(260, 480, 0x58188D))

    assert open_ascension_tab(game) is True
    assert fake.clicks() == [(95, 90), (93, 680), (95, 90), (93, 680)]
    assert "Shop click retried" in event_names()


def test_open_ascension_tab_never_clicks_the_ascension_button_while_the_panel_is_open(game, fake) -> None:
    fake.paint(538, 681, 0xAD1111)  # the panel's X tab: open, here on the tree, where (95, 90) is "Buy on Click"

    assert open_ascension_tab(game) is False
    assert (95, 90) not in fake.clicks()


def test_auto_upgrade_clicks_the_shop_button_again_when_a_click_is_lost(game, fake, event_names,
                                                                        monkeypatch) -> None:
    ignore_first_click_at(fake, 1163, 655, lambda: fake.paint(807, 145, 0xFFFFFF))
    shop = Shop(game)
    bought = []
    monkeypatch.setattr(shop, "buy_upgrade", lambda: bought.append(True))
    shop.auto_upgrade()

    assert bought and fake.clicks().count((1163, 655)) == 2
    assert "Shop click retried" in event_names()


def test_buy_upgrade_clicks_the_tab_again_when_a_click_is_lost(game, fake, event_names) -> None:
    ignore_first_click_at(fake, 927, 683, lambda: show_tab(fake, "upgrades"))
    shop = Shop(game)
    shop.loop_amount = 6
    shop.dailies_day = shop_module.daily_quests_day()  # no Quests visit for the "+2"
    shop.buy_upgrade()

    assert fake.clicks().count((927, 683)) == 2
    assert "Shop click retried" in event_names() and "Shop tab not shown" not in event_names()


def test_claim_quests_stops_scrolling_up_while_the_list_bounces_at_the_top(game, fake) -> None:
    fake.paint(807, 145, 0xFFFFFF)  # shop open...
    show_tab(fake, "quests")         # ...on the Quests tab
    fake.paint(1000, 690, 0xED8C18)  # the Quests tab glows: something to claim
    fake.paint(1254, 160, 0xB7B7B7)  # thumb at the top of the track...
    fake.paint(1254, 267, 0xA0A0A0)  # ...but shrunk by the elastic overscroll, so 267 shows the track
    notches_up = []
    fake.on_action = lambda a: notches_up.append(1) if a == ("button", 4, True) else None
    Shop(game).claim_quests()

    assert len(notches_up) == 20  # one round; the original's check at y = 267 kept wheeling (blank panel)


def paint_box(fake) -> None:
    """A floating silver Random Box over the player (its slate frame, 5F6D95)."""
    fake.paint(140, 310, 0x5F6D95, w=20, h=10)


def test_buy_upgrade_stops_for_a_floating_box(game, fake) -> None:
    show_tab(fake, "upgrades")
    buying_removes_rows(fake, ["buy", "buy", "buy", "red"])
    removing = fake.on_action

    def box_after_first_buy(action: tuple) -> None:
        removing(action)
        if action == client_click(1180, 170):
            paint_box(fake)

    fake.on_action = box_after_first_buy
    shop = Shop(game)
    shop.loop_amount = 6

    with pytest.raises(BoxOnScreen):
        shop.buy_upgrade()
    assert fake.clicks().count((1180, 170)) == 1  # it stopped buying after the box appeared


def test_auto_upgrade_closes_the_shop_and_reports_a_box(game, fake, event_names, monkeypatch) -> None:
    fake.paint(807, 145, 0xFFFFFF)  # the shop opens
    shop = Shop(game)

    def buy_until_a_box() -> None:
        raise BoxOnScreen

    monkeypatch.setattr(shop, "buy_upgrade", buy_until_a_box)

    assert shop.auto_upgrade() is False
    assert fake.clicks()[-1] == (1222, 677)  # closed the shop so the player can jump
    assert "Shopping stopped for a Random Box" in event_names()


def test_buy_equipment_stops_for_a_floating_box(game, fake) -> None:
    show_tab(fake, "upgrades")

    def switch_to_armor(action: tuple) -> None:
        if action == client_click(850, 690):
            fake.paint(897, 700, 0x883424)
            show_tab(fake, "armor")
            paint_box(fake)

    fake.on_action = switch_to_armor
    with pytest.raises(BoxOnScreen):
        Shop(game).buy_equipment()

    assert (1180, 636) not in fake.clicks()  # no "Max" and no equipment bought once the box showed


def test_buy_upgrade_checks_the_whole_row_it_clicks(game, fake) -> None:
    """The list scrolled by one notch: the row under the click point (y = 170) is cut off at the
    list's top, and its Vertical Magnet icon is above the original's check box (y 170-242)."""
    show_tab(fake, "upgrades")
    buying_removes_rows(fake, ["vm", "buy", "red"], first_separator=103)  # separators at 103 (hidden), 199, 295
    paint_rows(fake, ["vm", "buy", "red"], first_separator=103)
    fake.paint(885, 155, 0xF4B41B, w=20, h=6)  # the visible tail of the magnet icon, at the list's top
    shop = Shop(game)
    shop.loop_amount = 6
    shop.buy_upgrade()

    assert (1180, 170) not in fake.clicks()  # never click a row it can't see whole
    assert fake.clicks().count((1180, 266)) == 1  # the next, fully visible row


def test_buy_upgrade_waits_for_the_list_to_update_after_a_click(game, fake) -> None:
    show_tab(fake, "upgrades")
    rows = ["buy", "vm", "red"]
    paint_rows(fake, rows)
    pending: list[float] = []
    fake.on_action = lambda a: pending.append(fake.t + 300) if a == client_click(1180, 170) else None
    real_grab = fake.grab

    def grab(x: int, y: int, w: int, h: int):
        if pending and fake.t >= pending[0]:  # the game removes the bought row 300 ms later
            pending.clear()
            del rows[0]
            paint_rows(fake, rows)
        return real_grab(x, y, w, h)

    fake.grab = grab
    shop = Shop(game)
    shop.loop_amount = 6
    shop.buy_upgrade()

    assert fake.clicks().count((1180, 170)) == 1  # not clicked again before the list moved up


def test_row_around_rejects_a_click_point_outside_the_row_it_found(game, fake) -> None:
    show_tab(fake, "upgrades")
    paint_rows(fake, ["buy"])  # one row (156-248) and its closing separator (249-251)...
    fake.paint(800, 249, 0x454545, w=472, h=3)  # ...here hidden, as seen at the end of a short list

    assert Shop(game).row_around(170) == (156, 248)
    assert Shop(game).row_around(266) is None  # the nearest separator above belongs to another row


@pytest.mark.parametrize(("name", "expected"), [
    ("panel", None),         # no dialog yet: the confirm point is empty panel
    ("confirm", 0x00A400),   # "Are you sure?"
    ("cant", 0xAF0000),      # "You can't Ascend"
])
def test_ascend_dialog_on_recorded_frames(game, fake, name: str, expected: int | None) -> None:
    """Recorded on 2026-10-23 (a manual ascension with the Ultra Ascension node bought)."""
    fake.frame[190:560, 580:700] = read_png(Path(__file__).parent / "fixtures" / "ascend" / f"{name}.png")

    assert Shop(game).ascend_dialog() == expected


def test_sample_ascend_bonus_reads_and_logs_the_bonus_then_closes_the_panel(game, fake, events) -> None:
    panel = read_png(Path(__file__).parent / "fixtures" / "ascend_bonus" / "one-15.png")

    def open_tab(action: tuple) -> None:
        if action == client_click(93, 680):
            fake.frame[440:600, 80:450] = panel

    fake.on_action = open_tab

    assert Shop(game).sample_ascend_bonus() == 15.0
    assert fake.clicks() == [(95, 90), (93, 680), (570, 694)]
    assert [r for r in events() if r["event"] == "Ascend bonus"][0]["percent"] == 15.0
    assert not [r for r in events() if r["event"] == "frame"]


@pytest.mark.parametrize(("target", "closed"), [(10, False), (15, False), (20, True)])
def test_sample_ascend_bonus_keeps_the_panel_open_for_an_ascension(game, fake, target: float,
                                                                   closed: bool) -> None:
    # Closing it and opening it again right away lost the click 4 times of 7 on 2026-10-26.
    panel = read_png(Path(__file__).parent / "fixtures" / "ascend_bonus" / "one-15.png")
    fake.on_action = lambda a: fake.frame.__setitem__((slice(440, 600), slice(80, 450)), panel) \
        if a == client_click(93, 680) else None

    assert Shop(game).sample_ascend_bonus(keep_open_at=target) == 15.0
    assert ((570, 694) in fake.clicks()) is closed


def test_sample_ascend_bonus_saves_a_frame_it_cannot_read(game, fake, events) -> None:
    fake.on_action = lambda a: fake.paint(260, 480, 0x58188D) if a == client_click(93, 680) else None

    assert Shop(game).sample_ascend_bonus() is None
    assert "Ascend bonus unreadable" in [r["event"] for r in events()]
    assert [r["label"] for r in events() if r["event"] == "frame"] == ["ascend-bonus-unreadable"]


def test_sample_ascend_bonus_reports_a_panel_that_doesnt_show(game, fake, event_names) -> None:
    assert Shop(game).sample_ascend_bonus() is None
    assert fake.clicks()[-1] == (570, 694)
    assert "Ascend bonus not shown" in event_names()


def test_buy_upgrade_buys_a_claimed_quest_reward_row(game, fake, event_names) -> None:
    """A claimed event-quest reward stays blue but gets a green "Unlock" button (Dracula's Tooth,
    2026-10-23): it is bought like any upgrade."""
    show_tab(fake, "upgrades")
    paint_upgrades(fake, 1, 0, reward_button=0x11A622)
    fake.on_action = lambda a: paint_upgrades(fake, 0, 0, buyable=False) if a == client_click(1180, 170) else None
    shop = Shop(game)
    shop.loop_amount = 6
    shop.buy_upgrade()

    assert fake.clicks().count((1180, 170)) == 1
    assert ("button", 5, True) not in fake.actions  # no scrolling past it
    assert "Quest Reward rows skipped" not in event_names()


@pytest.mark.parametrize(("name", "expected"), [
    ("reward-unclaimed", 266),  # Chocolate Bar, grey "Quest Reward" (2026-10-22): start at the 2nd row
    ("reward-buyable", 170),    # Dracula's Tooth, green "Unlock 200 Sx" (2026-10-23): buy it
])
def test_first_row_after_quest_rewards_on_recorded_frames(game, fake, name: str, expected: int) -> None:
    fake.frame[115:585, 800:1270] = read_png(Path(__file__).parent / "fixtures" / "quest_rewards" / f"{name}.png")

    assert first_row_after_quest_rewards(game) == expected  # the fake list can't scroll: it stays put


@pytest.mark.parametrize(("name", "claimable"), [("6-quests-gold", True), ("6-quests", False),
                                                 ("6-upgrades", False), ("6-armor", False)])
def test_quests_glow_on_recorded_tab_bars(game, fake, name: str, claimable: bool) -> None:
    # The Quests tab's icon at (1000, 690): E03C28 at rest (639 recorded frames); it pulses towards
    # ED8C18 about once a second while something can be claimed (2026-10-22).
    paint_tab_bar(fake, name)

    assert Shop(game).quests_claimable() is claimable


def test_claim_quests_without_a_glowing_quests_tab_claims_nothing(game, fake, event_names) -> None:
    # The shop button also glows for other things: claims ran with nothing to claim (2026-10-23).
    fake.paint(807, 145, 0xFFFFFF)
    show_tab(fake, "quests")
    fake.paint(1160, 300, 0x11A622)
    Shop(game).claim_quests()

    assert "Claim quests: nothing to claim" in event_names()
    assert (1160, 300) not in fake.clicks() and (1000, 690) not in fake.clicks()
    assert fake.clicks()[-1] == (1244, 712)


def test_a_buy_claims_quests_in_the_same_visit(game, fake, monkeypatch) -> None:
    shop = Shop(game)
    shop.dailies_day = shop_module.daily_quests_day()  # the "+2" was already looked for today
    claimed = []
    monkeypatch.setattr(shop, "claim_in_shop", lambda: claimed.append(fake.t))
    show_tab(fake, "upgrades")
    fake.paint(1000, 690, 0xED8C18)
    shop.finish_visit()

    assert claimed and fake.clicks()[-1] == (1222, 677)

    claimed.clear()
    fake.paint(1000, 690, 0xE03C28)  # at rest
    shop.finish_visit()
    assert not claimed


def test_buy_upgrade_ends_its_visit_through_finish_visit(game, fake, monkeypatch) -> None:
    show_tab(fake, "upgrades")
    shop = Shop(game)
    shop.loop_amount = 6  # no equipment round
    finished = []
    monkeypatch.setattr(shop, "finish_visit", lambda: finished.append(True))
    shop.buy_upgrade()

    assert finished == [True]


def test_claim_clicks_each_button_once(game, fake) -> None:
    # The button stays green a moment after the click: it was clicked 2-3 times, ~21 ms apart.
    fake.paint(807, 145, 0xFFFFFF)
    show_tab(fake, "quests")
    fake.paint(1000, 690, 0xED8C18)
    fake.paint(1160, 300, 0x11A622)
    clicked_at = []
    fake.on_action = lambda a: clicked_at.append(fake.t) if a == client_click(1160, 300) else None
    grab = fake.grab

    def button_goes_after_60_ms(x: int, y: int, w: int, h: int):
        if clicked_at and fake.t >= clicked_at[0] + 60:
            fake.paint(1160, 300, 0)
        return grab(x, y, w, h)

    fake.grab = button_goes_after_60_ms
    Shop(game).claim_quests()

    assert fake.clicks().count((1160, 300)) == 1


def paint_daily_quests_header(fake, name: str) -> None:
    """The Daily Quests header recorded under Phantom Fall's event quests (client x 800-1269, y 420-479):
    "plus-2" with the free "+2" button (2026-10-27), "taken" after the user clicked it (2026-10-26)."""
    fake.frame[420:480, 800:1270] = read_png(Path(__file__).parent / "fixtures" / "daily_quests" / f"{name}.png")


@pytest.mark.parametrize(("name", "button"), [("plus-2", True), ("taken", False)])
def test_extra_daily_quests_button_on_recorded_frames(game, fake, event_names, name: str, button: bool) -> None:
    paint_daily_quests_header(fake, name)
    fake.on_action = lambda a: fake.paint(1179, 466, 0x2A1203, w=67, h=32) if a[0] == "click" else None  # gone
    Shop(game).take_extra_dailies()

    assert fake.clicks() == ([(1188, 481)] if button else [])
    assert ("Extra daily quests taken" in event_names()) is button
    assert "Extra daily quests click had no effect" not in event_names()


def test_extra_daily_quests_are_clicked_once_a_day_even_when_the_button_stays(game, fake, event_names) -> None:
    paint_daily_quests_header(fake, "plus-2")
    shop = Shop(game)
    shop.take_extra_dailies()
    shop.take_extra_dailies()

    assert fake.clicks() == [(1188, 481)]
    assert "Extra daily quests click had no effect" in event_names()


def test_extra_daily_quests_darkened_under_the_pointer_is_still_there(game, fake, event_names) -> None:
    # Live 2026-10-28 21:43: under the pointer the button turns 266E26 at once; it only goes later. A lost
    # click leaves it darkened like that.
    paint_daily_quests_header(fake, "plus-2")
    fake.on_action = lambda a: fake.paint(1179, 466, 0x266E26, w=67, h=32) if a[0] == "click" else None
    Shop(game).take_extra_dailies()

    assert "Extra daily quests click had no effect" in event_names()


def test_extra_daily_quests_at_the_list_top_are_taken(game, fake) -> None:
    # Without event quests the Daily Quests header is the list's first row (Santi, 2026-10-28): the button
    # sits right under the list's top edge (AutoIt y 156).
    fake.paint(1179, 162, 0x379D37, w=67, h=32)
    Shop(game).take_extra_dailies()

    assert fake.clicks() == [(1188, 177)]


def test_extra_daily_quests_button_cut_off_by_the_list_top_is_not_clicked(game, fake) -> None:
    # Only its bottom shows: 15 px under the first green pixel is the Reroll button of the first daily quest.
    paint_daily_quests_header(fake, "plus-2")
    fake.paint(1179, 466, 0x000000, w=67, h=25)
    Shop(game).take_extra_dailies()

    assert fake.clicks() == []


def test_claiming_takes_the_extra_daily_quests(game, fake) -> None:
    fake.paint(807, 145, 0xFFFFFF)  # the shop is open
    show_tab(fake, "quests")
    fake.paint(1000, 690, 0xED8C18)  # the Quests tab glows: something to claim
    paint_daily_quests_header(fake, "plus-2")
    Shop(game).claim_quests()

    assert (1188, 481) in fake.clicks()


def test_a_buy_visits_the_quests_tab_once_a_daily_quests_day(game, fake, monkeypatch) -> None:
    # Even with nothing to claim, for the "+2" Daily Quests button.
    day = [20390]
    monkeypatch.setattr(shop_module, "daily_quests_day", lambda: day[0])
    show_tab(fake, "quests")
    fake.paint(1000, 690, 0xE03C28)  # the Quests tab at rest: nothing to claim
    shop = Shop(game)
    shop.finish_visit()
    shop.finish_visit()
    day[0] += 1
    shop.finish_visit()

    assert fake.clicks().count((1000, 690)) == 2


def test_claim_quests_stops_for_a_floating_box(game, fake, event_names) -> None:
    # 2026-10-28 00:24:09-12: a silver box hovered over the player for 3.5 s while the claim loop scrolled
    # the Quests list, and was lost.
    fake.paint(807, 145, 0xFFFFFF)  # the shop is open
    show_tab(fake, "quests")
    fake.paint(1000, 690, 0xED8C18)  # the Quests tab glows: something to claim
    fake.paint(1160, 300, 0x11A622)
    paint_box(fake)
    Shop(game).claim_quests()

    assert (1160, 300) not in fake.clicks()
    assert "Shopping stopped for a Random Box" in event_names()
    assert fake.clicks()[-1] == (1244, 712)  # closed the shop so the player can jump


def test_buy_upgrade_waits_for_the_list_to_settle_at_the_top(game, fake) -> None:
    """2026-11-06 00:21:26: 0.4 s after the wheel the list was still bouncing back to the top, no separator in
    y 153-170, and the first row (Chaos Necklace) was taken for cut off and left for a later round (18 of 192 visits)."""
    show_tab(fake, "upgrades")
    paint_rows(fake, ["buy", "red"], first_separator=175)  # bounced past the top
    real_grab = fake.grab

    def grab(x: int, y: int, w: int, h: int):
        if fake.t >= 700:
            paint_rows(fake, ["buy", "red"])  # settled
        return real_grab(x, y, w, h)

    fake.grab = grab
    shop = Shop(game)
    shop.loop_amount = 6
    shop.buy_upgrade()

    assert (1180, 170) in fake.clicks()
