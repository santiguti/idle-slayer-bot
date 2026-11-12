from dataclasses import replace
from pathlib import Path

import pytest

from idle_runner import minions
from idle_runner.config import Settings
from idle_runner.minions import (AWAY, CLAIM, EARNED_TEXT_MS, SUFFIXED_SP_MIN, buttons, daily_bonus_shown, mission_ms,
                                 read_available_sp, read_mission_cost, send_buttons, send_minions, Visit)
from tests.fakes import OFFSET, read_png

FIXTURES = Path(__file__).parent / "fixtures" / "minions"
# The two minions' buttons in send-526.png (black box 2026-10-28 00:17:10): AutoIt y of their top edge.
WHITE_KNIGHT, DARK_WIZARD = 222 + 31, 372 + 31


def show_panel(fake, name: str) -> None:
    """A Minions tab recorded live (client x 0-639): "send-526" with both minions ready to send and
    526 SP available (black box 2026-10-28), "away-1676" with both on a mission (Santi's screenshot)."""
    fake.frame[:, :640] = read_png(FIXTURES / f"{name}.png")


@pytest.mark.parametrize(("name", "expected"), [("send-526", 526), ("away-1676", 1_676)])
def test_reads_the_available_sp_in_the_minions_tab(game, fake, name: str, expected: int) -> None:
    show_panel(fake, name)

    assert read_available_sp(game) == expected


def test_reads_an_available_sp_with_a_thousands_comma(game, fake) -> None:
    # The tree tab's header ("21,048 available", black box 2026-10-28 00:45:11) sits further right.
    fake.frame[20:65, :640] = read_png(FIXTURES / "tree-header-21048.png")

    assert read_available_sp(game) == 21_048


def test_no_panel_reads_no_sp(game, fake) -> None:
    assert read_available_sp(game) is None


def test_finds_whole_send_buttons_and_reads_their_cost(game, fake) -> None:
    show_panel(fake, "send-526")

    assert send_buttons(game) == [WHITE_KNIGHT, DARK_WIZARD]
    assert [read_mission_cost(game, top) for top in send_buttons(game)] == [10, 150]


def test_minions_on_a_mission_have_no_send_button(game, fake) -> None:
    show_panel(fake, "away-1676")

    assert send_buttons(game) == []


def in_button(click: tuple[int, int], top: int) -> bool:
    return 423 <= click[0] <= 621 and top <= click[1] <= top + 122


def play_minions_tab(fake, monkeypatch, available: int | None, takes_effect: bool = True) -> list[int]:
    """The ascension panel opens, its Minions tab shows send-526, and a click on a send button sends that
    minion: the button turns "On a Mission..." and its cost leaves the header's SP. Returns the costs sent."""
    sent: list[int] = []
    costs = {WHITE_KNIGHT: 10, DARK_WIZARD: 150}

    def act(action: tuple) -> None:
        if action[0] != "click":
            return
        click = (action[1] + OFFSET[0], action[2] + OFFSET[1])
        if click == (95, 90):  # the ascension button opens the panel on its Ascension tab
            fake.paint(538, 681, 0xAD1111)
            fake.paint(260, 480, 0x58188D)
        elif click == (332, 680):  # the Minions tab
            show_panel(fake, "send-526")
        for top, cost in costs.items():
            if in_button(click, top) and takes_effect:
                fake.paint(410, top, 0x975DCA, w=29, h=123)
                sent.append(cost)

    fake.on_action = act
    monkeypatch.setattr(minions, "read_available_sp",
                        lambda game: None if available is None else available - sum(sent))
    return sent


def test_sends_every_minion_the_sp_covers(game, fake, monkeypatch, event_names) -> None:
    sent = play_minions_tab(fake, monkeypatch, available=526)

    assert send_minions(game) == Visit([10, 150], bonus=False)  # the costs it sent: they tell when each mission ends
    assert sent == [10, 150]
    assert event_names().count("Minion sent") == 2
    assert fake.clicks()[-1] == (570, 694)  # closed the panel


def test_never_clicks_a_mission_the_sp_does_not_cover(game, fake, monkeypatch, events) -> None:
    # Without enough SP the game may offer to pay the rest with jewels, as the tree did on 2026-10-26.
    sent = play_minions_tab(fake, monkeypatch, available=100)
    send_minions(game)

    assert sent == [10]
    assert not [c for c in fake.clicks() if in_button(c, DARK_WIZARD)]
    skipped = [r for r in events() if r["event"] == "Minion not sent"]
    assert skipped and skipped[-1]["reason"] == "not enough SP" and skipped[-1]["cost"] == 150


def test_unreadable_sp_sends_nothing(game, fake, monkeypatch, event_names) -> None:
    play_minions_tab(fake, monkeypatch, available=None)
    send_minions(game)

    assert not [c for c in fake.clicks() if in_button(c, WHITE_KNIGHT) or in_button(c, DARK_WIZARD)]
    assert "Minions SP not readable" in event_names()


def test_a_send_without_effect_is_not_clicked_again(game, fake, monkeypatch, events) -> None:
    play_minions_tab(fake, monkeypatch, available=526, takes_effect=False)
    send_minions(game)

    assert len([c for c in fake.clicks() if in_button(c, WHITE_KNIGHT) or in_button(c, DARK_WIZARD)]) == 1
    assert any(r["event"] == "Minion not sent" and r["reason"] == "no effect" for r in events())


def test_nothing_is_clicked_without_the_minions_tab(game, fake, event_names) -> None:
    # After an Ultra Ascension there is no Minions tab until the node is bought again: (332, 680) is the
    # empty tab bar (3E260A), and clicks meant for minions would land in the tree.
    def act(action: tuple) -> None:
        if action == ("click", 95 - 8, 90 - 31):
            fake.paint(538, 681, 0xAD1111)
            fake.paint(260, 480, 0x58188D)
        elif action == ("click", 332 - 8, 680 - 31):
            fake.paint(332, 676, 0x3E260A)

    fake.on_action = act
    send_minions(game)

    assert fake.clicks() == [(95, 90), (93, 680), (332, 680), (332, 680), (570, 694)]  # retried once
    assert "Minions tab not shown" in event_names()


def test_a_tab_without_known_buttons_is_kept_for_a_look(game, fake, monkeypatch, events) -> None:
    # Buttons that are neither Send, On a Mission nor Claim: keep a frame to see what they are.
    play_minions_tab(fake, monkeypatch, available=526)
    send_panel = fake.on_action

    def other_buttons(action: tuple) -> None:
        send_panel(action)
        if action == ("click", 332 - 8, 680 - 31):
            fake.paint(410, WHITE_KNIGHT, 0x7A7A7A, w=29, h=123)
            fake.paint(410, DARK_WIZARD, 0x7A7A7A, w=29, h=123)

    fake.on_action = other_buttons
    send_minions(game)

    assert "Minions buttons unknown" in [r["event"] for r in events()]
    assert any(r["event"] == "frame" and r["label"] == "minions-buttons-unknown" for r in events())


def finished_white_knight(fake, monkeypatch, claim_takes_effect: bool = True) -> list[int]:
    """send-526 with the White Knight back from its mission: a green "Claim" button (11A622, Santi
    2026-10-28: the shop's Unlock green). Claiming turns it into "Send on Mission"."""
    sent = play_minions_tab(fake, monkeypatch, available=526)
    send_panel = fake.on_action

    def act(action: tuple) -> None:
        click = (action[1] + OFFSET[0], action[2] + OFFSET[1]) if action[0] == "click" else None
        if click and in_button(click, WHITE_KNIGHT) and fake.frame[WHITE_KNIGHT - 31, 430][1] == 0xA6:
            if claim_takes_effect:
                fake.paint(410, WHITE_KNIGHT, 0x541787, w=29, h=123)
            return
        send_panel(action)
        if action == ("click", 332 - 8, 680 - 31):
            fake.paint(410, WHITE_KNIGHT, 0x11A622, w=29, h=123)

    fake.on_action = act
    return sent


def test_claims_a_finished_mission_then_sends_the_minion_again(game, fake, monkeypatch, event_names) -> None:
    sent = finished_white_knight(fake, monkeypatch)
    send_minions(game)

    knight_clicks = [c for c in fake.clicks() if in_button(c, WHITE_KNIGHT)]
    assert len(knight_clicks) == 2  # the claim, then the send
    assert "Minion claimed" in event_names()
    assert sent == [10, 150]


BOXES = Path(__file__).parent / "fixtures" / "boxes"


def test_a_box_beside_the_panel_cuts_the_visit_short(game, fake, monkeypatch, event_names) -> None:
    # Live 2026-11-12 00:36: a Random Box floated past the open Minions tab while the jumper waited, and was lost.
    sent = play_minions_tab(fake, monkeypatch, available=526)
    send_panel = fake.on_action

    def act(action: tuple) -> None:
        send_panel(action)
        if sent == [10]:  # the White Knight went: a box flies in beside the panel
            fake.frame[100:480, 640:1280] = read_png(BOXES / "beside-panel-silver.png")

    fake.on_action = act

    assert send_minions(game) == Visit([10], bonus=False, box=True)  # the White Knight's mission is still counted
    assert sent == [10] and not [c for c in fake.clicks() if in_button(c, DARK_WIZARD)]
    assert fake.clicks()[-1] == (570, 694)  # closed the panel: the jumper can get the box
    assert "Minions visit cut short" in event_names()


def test_a_box_during_the_earned_text_cuts_the_visit_short_at_once(game, fake, monkeypatch) -> None:
    # The "N earned" wait is 2.5 s, most of the ~3 s a box shows beside the panel.
    sent = finished_white_knight(fake, monkeypatch)
    claim_panel = fake.on_action
    claimed_at: list[float] = []

    def act(action: tuple) -> None:
        if action[0] == "click" and in_button((action[1] + OFFSET[0], action[2] + OFFSET[1]), WHITE_KNIGHT):
            claimed_at.append(fake.t)
        claim_panel(action)

    fake.on_action = act
    monkeypatch.setattr(minions, "box_beside_panel", lambda g: bool(claimed_at) and fake.t >= claimed_at[0] + 1000)

    visit = send_minions(game)

    assert visit.box and sent == []  # the White Knight was claimed, then the visit ended
    closed_at = next(a for a in reversed(fake.actions) if a[0] == "click")
    assert closed_at == ("click", 570 - 8, 694 - 31)
    assert fake.t - claimed_at[0] < 1000 + 2 * minions.BOX_POLL_MS


def test_a_claim_without_effect_is_not_clicked_again(game, fake, monkeypatch, event_names) -> None:
    finished_white_knight(fake, monkeypatch, claim_takes_effect=False)
    send_minions(game)

    assert len([c for c in fake.clicks() if in_button(c, WHITE_KNIGHT)]) == 1
    assert "Minion not claimed" in event_names()


@pytest.mark.parametrize(("divinities", "minutes"), [
    ((), 180),
    (("work_benefits", "improved_work_conditions"), 117),  # wiki: "under 2 hours" with these two
    (("work_benefits", "improved_work_conditions", "greeks_blessing"), 72),
])
def test_a_white_knight_mission_lasts_3_hours_less_the_divinities(divinities: tuple[str, ...], minutes: int) -> None:
    settings = replace(Settings(), **{name: True for name in divinities})

    assert mission_ms(10, settings) == pytest.approx(minutes * 60_000)


def test_each_mission_cost_tells_its_length() -> None:
    # Wiki, Minions: White Knight 10 SP 3h00m, Dark Wizard 150 SP 6h30m, Skeleton 1,000 SP 3h00m,
    # Goo Mutant 1,500 SP 4h30m, Stone Golem 3,000 SP 23h00m.
    assert [mission_ms(cost, Settings()) for cost in (10, 150, 1_000, 1_500, 3_000)] == [
        m * 60_000 for m in (180, 390, 180, 270, 1_380)]
    assert mission_ms(42, Settings()) is None


def test_minions_right_after_the_tree_reuse_its_open_panel(game, fake, monkeypatch) -> None:
    # The tree leaves the panel open; the ascension button there is the tree's "Buy on Click" toggle.
    sent = play_minions_tab(fake, monkeypatch, available=526)
    fake.paint(538, 681, 0xAD1111)  # the panel's X tab: open, on the tree tab
    fake.paint(260, 480, 0x58188D)  # what the Ascension tab shows once clicked
    send_minions(game)

    assert (95, 90) not in fake.clicks()
    assert fake.clicks()[0] == (93, 680) and sent == [10, 150]


def test_waits_for_the_minions_tab_to_fade_in(game, fake, monkeypatch) -> None:
    # Live 2026-10-28 02:43: right after the tree, the Ascension and Minions tab clicks came 28 ms apart; the
    # Minions list showed, but 200 ms after the click its tab wasn't the selected shade yet.
    sent = play_minions_tab(fake, monkeypatch, available=526)
    act, grab, due = fake.on_action, fake.grab, []

    def tab_late(action: tuple) -> None:
        if action[0] == "click" and (action[1] + OFFSET[0], action[2] + OFFSET[1]) == (332, 680):
            due.append(fake.t + 400)
            return
        act(action)

    def grab_late(x: int, y: int, w: int, h: int):
        if due and fake.t >= due[0]:
            due.clear()
            show_panel(fake, "send-526")
        return grab(x, y, w, h)

    fake.on_action, fake.grab = tab_late, grab_late
    send_minions(game)

    assert sent == [10, 150]


def test_finds_the_buttons_with_the_game_in_spanish(game, fake) -> None:
    # "Realizando una Misión ..." (2026-10-28) is wider than "On a Mission...": the column the buttons were
    # found on crossed its letters. Three whole buttons; the fourth is cut off by the tab bar.
    show_panel(fake, "es-away-96954")

    assert send_buttons(game, minions.AWAY) == [151, 301, 451]
    assert read_available_sp(game) == 96_954


def test_reads_the_cost_with_the_game_in_spanish(game, fake) -> None:
    # "Dar Misión (-1,000 SP)": the cost is the second of two lines (the third in English), and the list's
    # scrollbar sits right of the button (2026-10-28, after an ascension: Skeleton and Goo Mutant to send).
    show_panel(fake, "es-send-149022")

    assert send_buttons(game) == [151, 451]
    assert [read_mission_cost(game, top) for top in send_buttons(game)] == [1_000, 1_500]
    assert read_available_sp(game) == 149_022


def five_minions(fake, start: str = "claim-cut-765038") -> list[tuple[int, int]]:
    """Five minions, more than the list shows (2026-10-28): at its top (black box 20:18) Skeleton, White Knight
    and Goo Mutant are on a mission and the Dark Wizard's "Claim Reward" is cut off by the tab bar; scrolled to its
    bottom (20:37) the claim is whole, with the Stone Golem under it. Returns the clicks on that claim."""
    claims: list[tuple[int, int]] = []

    def act(action: tuple) -> None:
        if action[0] == "click":
            click = (action[1] + OFFSET[0], action[2] + OFFSET[1])
            if click == (95, 90):
                fake.paint(538, 681, 0xAD1111)
                fake.paint(260, 480, 0x58188D)
            elif click == (332, 680):
                show_panel(fake, start)
                # The tab pulses gold while a claim waits (20:18 caught it gold); the pulse's dark end is the
                # selected shade (20:37).
                fake.paint(332, 676, 0x5E261B)
            elif in_button(click, 372) and fake.frame[372 - 31, 430][1] == 0xA6:
                claims.append(click)
                fake.paint(410, 372, 0x975DCA, w=29, h=123)
        elif action == ("button", 5, True):  # wheel down
            show_panel(fake, "claim-bottom-765038")
        elif action == ("button", 4, True):  # wheel up
            show_panel(fake, "claim-cut-765038")

    fake.on_action = act
    return claims


def test_scrolls_down_to_a_claim_the_list_cut_off(game, fake, event_names) -> None:
    # Live 2026-10-28 20:18 and 20:19: the bot looked at the list's top twice and never saw the Dark Wizard's claim.
    claims = five_minions(fake)
    send_minions(game)

    assert len(claims) == 1
    assert "Minion claimed" in event_names()


def test_scrolls_to_the_top_first(game, fake) -> None:
    # The game keeps the list where it was left: at 20:37 it was at the bottom, Skeleton out of sight.
    five_minions(fake, start="claim-bottom-765038")
    send_minions(game)

    wheel = [a[1] for a in fake.actions if a[0] == "button" and a[1] in (4, 5) and a[2]]
    assert wheel[0] == 4  # up


def test_a_short_list_is_not_scrolled_down(game, fake, monkeypatch) -> None:
    play_minions_tab(fake, monkeypatch, available=526)
    send_minions(game)

    assert ("button", 5, True) not in fake.actions


def test_a_lost_minions_tab_click_is_retried(game, fake, monkeypatch, event_names) -> None:
    # Live 2026-10-28 19:25: the panel was already on the Minions tab; the Ascension tab click switched the list
    # away at once but its shade stayed on Minions, and the Minions click 24 ms later was lost. The shade said
    # "Minions" over the Ascension tab: nothing was sent.
    sent = play_minions_tab(fake, monkeypatch, available=526)
    show_panel(fake, "send-526")  # open on the Minions tab, its shade included
    fake.paint(538, 681, 0xAD1111)
    act, last_tab_click = fake.on_action, [-1.0]

    def tab_switch_swallows_clicks(action: tuple) -> None:
        if action[0] != "click":
            return act(action)
        click = (action[1] + OFFSET[0], action[2] + OFFSET[1])
        if click == (93, 680):  # the Ascension tab: its list, the Minions shade stays a while
            fake.paint(410, 136, 0x3A3A3A, w=200, h=520)
            fake.paint(260, 480, 0x58188D)
            last_tab_click[0] = fake.t
        elif click == (332, 680) and fake.t - last_tab_click[0] < 100:
            return  # lost
        else:
            act(action)

    fake.on_action = tab_switch_swallows_clicks
    send_minions(game)

    assert sent == [10, 150]
    assert "Shop click retried" in event_names()


@pytest.mark.parametrize(("name", "shown"), [("daily-bonus", True), ("daily-bonus-taken", False), ("away-1676", False),
                                             ("claim-cut-765038", False)])
def test_the_daily_bonus_banner_on_recorded_frames(game, fake, name: str, shown: bool) -> None:
    show_panel(fake, name)

    assert daily_bonus_shown(game) is shown


def play_daily_bonus(fake, takes_effect: bool = True) -> None:
    """The Minions tab with the Daily Bonus banner, Skeleton, White Knight and Goo Mutant on missions (live
    2026-10-28 21:43). A click on the banner takes 3 hours off them: the banner goes and three claims show."""
    def act(action: tuple) -> None:
        if action[0] != "click":
            return
        click = (action[1] + OFFSET[0], action[2] + OFFSET[1])
        if click == (95, 90):
            fake.paint(538, 681, 0xAD1111)
            fake.paint(260, 480, 0x58188D)
        elif click == (332, 680):
            show_panel(fake, "daily-bonus")
        elif click == (328, 191) and takes_effect:
            show_panel(fake, "daily-bonus-taken")

    fake.on_action = act


def test_takes_the_daily_bonus_after_sending_while_minions_are_away(game, fake, event_names) -> None:
    play_daily_bonus(fake)

    assert send_minions(game) == Visit([], bonus=True)
    assert fake.clicks()[-2:] == [(328, 191), (570, 694)]  # the banner, then the panel's X
    assert "Minions daily bonus taken" in event_names()


def test_a_daily_bonus_click_without_effect_is_reported(game, fake, event_names) -> None:
    play_daily_bonus(fake, takes_effect=False)

    assert send_minions(game) == Visit([], bonus=False)
    assert fake.clicks().count((328, 191)) == 1
    assert "Minions daily bonus click had no effect" in event_names()


def test_the_daily_bonus_waits_while_no_minion_is_away(game, fake, monkeypatch) -> None:
    # It only shortens missions that are running: with every minion home it would be wasted for the day.
    play_minions_tab(fake, monkeypatch, available=0)
    send_panel = fake.on_action

    def with_banner(action: tuple) -> None:
        send_panel(action)
        if action == ("click", 332 - 8, 680 - 31):
            fake.frame[108:211, :640] = read_png(FIXTURES / "daily-bonus.png")[108:211]

    fake.on_action = with_banner
    assert send_minions(game) == Visit([], bonus=False)
    assert (328, 191) not in fake.clicks()


# With the tree's "The Chosen One" each row has an orange Prestige box ("+N" Divinity Points) above a 67 px button
# (live 2026-11-03 00:11, five minions, 241 M SP): the Dark Wizard's button top in these frames, AutoIt y.
PRESTIGE_ROW = 396 + 31


def test_finds_whole_buttons_under_the_prestige_boxes(game, fake) -> None:
    show_panel(fake, "prestige-claim")  # Dark Wizard back; the top row is cut off by the header
    assert buttons(game, CLAIM) == [(PRESTIGE_ROW, 67)]
    assert send_buttons(game, AWAY) == [246 + 31, 546 + 31]


def test_reads_the_cost_of_a_send_button_under_a_prestige_box(game, fake) -> None:
    show_panel(fake, "prestige-send-150")
    assert send_buttons(game) == [PRESTIGE_ROW]
    assert read_mission_cost(game, PRESTIGE_ROW) == 150


@pytest.mark.parametrize("name", ["prestige-claim", "prestige-send-150", "prestige-away"])
def test_a_suffixed_sp_header_reads_as_its_lower_bound(game, fake, name: str) -> None:
    """ "241 M available": the game writes up to at least 9,482,458 in full (tree header 2026-10-30)."""
    show_panel(fake, name)
    assert read_available_sp(game) == SUFFIXED_SP_MIN


def prestige_tab(fake) -> list[tuple[int, int]]:
    """The Minions tab with the Prestige boxes: the Dark Wizard back from its mission; a claim turns its button into
    "Send on Mission (-150 SP)" and puts the "earned" text over the rows above for EARNED_TEXT_MS, a send turns it
    "On a Mission...". The header says "241 M" all along. Returns the clicks with the time they came."""
    clicks: list[tuple[int, int]] = []
    shown = {"until": 0.0}

    def act(action: tuple) -> None:
        if action[0] != "click":
            return
        click = (action[1] + OFFSET[0], action[2] + OFFSET[1])
        clicks.append((click[1], fake.t))
        if click == (95, 90):
            fake.paint(538, 681, 0xAD1111)
            fake.paint(260, 480, 0x58188D)
        elif click == (332, 680):
            show_panel(fake, "prestige-claim")
            fake.paint(332, 676, 0x5E261B)  # the tab pulses gold while a claim waits: its dark end
        elif 423 <= click[0] <= 621 and PRESTIGE_ROW <= click[1] < PRESTIGE_ROW + 67:
            if fake.t < shown["until"]:
                return  # the text over the list: nothing should be clicked meanwhile
            if fake.frame[PRESTIGE_ROW - 31, 402][1] == 0xA6:  # the claim
                show_panel(fake, "prestige-earned-text")
                shown["until"] = fake.t + EARNED_TEXT_MS - 100
            else:
                show_panel(fake, "prestige-away")

    def tick(action: tuple) -> None:
        if shown["until"] and fake.t >= shown["until"]:
            show_panel(fake, "prestige-send-150")
            shown["until"] = 0.0
        act(action)

    fake.on_action = tick
    return clicks


def test_claims_and_sends_a_minion_under_a_prestige_box(game, fake, event_names) -> None:
    clicks = prestige_tab(fake)
    sent = send_minions(game).sent

    names = event_names()
    assert "Minion claimed" in names and sent == [150]
    row = [(y, t) for y, t in clicks if PRESTIGE_ROW <= y < PRESTIGE_ROW + 67]
    assert [y for y, _ in row] == [PRESTIGE_ROW + 33, PRESTIGE_ROW + 33]  # the claim, then the send, in the middle
    assert row[1][1] - row[0][1] >= EARNED_TEXT_MS  # after the "earned" text went
    assert not [y for y, _ in clicks if PRESTIGE_ROW - 55 <= y < PRESTIGE_ROW - 15]  # never the Prestige box

