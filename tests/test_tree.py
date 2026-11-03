from pathlib import Path

import numpy as np
import pytest

from idle_runner.state import load_state, update_state
from idle_runner.tree import Tree, links, pan_shift
from idle_runner.tree_nodes import NODES, RECOMMENDED_ORDER
from tests.fakes import OFFSET, read_png

FIXTURES = Path(__file__).parent / "fixtures" / "tree"

ORDER = [(n, NODES[n].point) for n in RECOMMENDED_ORDER]


class FakeTree:
    """The ascension panel and its tree tab as measured on 2026-10-26, in AutoIt coordinates.

    A node click opens a modal: green Buy (468, 571) for a node whose prerequisites are met, red with the
    wide "Can't buy yet" text (white at 580, 582) for a locked one, red with "Close" for a bought one.
    Buy unlocks the node and closes the modal. For nodes in `poor` (not enough SP) it opens the offer to pay
    the difference with jewels instead (live, 2026-10-26): an unticked "I understand" box (white at 583, 521),
    the jewel button (094309 at 468, 571) and Close (758, 582). The modal dims the panel (its X tab at
    538, 681 turns 150202), and the dimming fades out for FADE_MS after the modal closes: clicks meanwhile
    are lost (live, 2026-10-26: the check after Village Key's Buy, 222 ms later).

    Hovering a node shows its tooltip: a 262626 box from x + 43, centred on the pointer, with "Cost: N" in
    11AA23 when the SP is enough and AD1111 when it isn't, next to the SP icon (6A31CA); a bought node's
    says "Unlocked", also 11AA23 (measured 2026-10-25). `tooltips=False` hides them; `lying_tooltips`
    shows green for every node. `press_ms` > 0: a purchase that goes through first shows the pressed Buy
    button for that long, in the jewel button's colour (live, 18:47 and 20:04 on 2026-10-26; its box
    stays dark).
    """

    FADE_MS = 300

    def __init__(self, fake, bought=(), locked=(), poor=(), tooltips: bool = True,
                 lying_tooltips: bool = False, press_ms: float = 0) -> None:
        self.fake = fake
        self.bought, self.locked, self.poor = set(bought), set(locked), set(poor)
        self.tooltips, self.lying_tooltips = tooltips, lying_tooltips
        self.modal_for: str | None = None
        self.jewel_offer = False
        self.box_ticked = False
        self.tooltip_at: tuple[int, int] | None = None
        self.panel_open = False
        self.fade_until = -1.0
        self.press_ms = press_ms
        self.bought_at: float | None = None  # when a pressed Buy goes through
        fake.on_action = self.act
        grab = fake.grab

        def grab_after_fade(x: int, y: int, w: int, h: int):
            if self.bought_at is not None and fake.t >= self.bought_at:
                self.bought_at = None
                self.bought.add(self.modal_for)
                self.hide()
            if self.panel_open and self.modal_for is None and fake.t >= self.fade_until:
                fake.paint(538, 681, 0xAD1111)
            return grab(x, y, w, h)

        fake.grab = grab_after_fade

    def act(self, action: tuple) -> None:
        if action[0] == "move":
            self.hover(action[1] + OFFSET[0], action[2] + OFFSET[1])
        if action[0] != "click" or self.fake.t < self.fade_until:
            return
        x, y = action[1] + OFFSET[0], action[2] + OFFSET[1]
        if (x, y) == (583, 521):
            self.box_ticked = True
        if (x, y) == (95, 90):  # the panel opens on its Ascension tab
            self.panel_open = True
            self.fake.paint(538, 681, 0xAD1111)
            self.fake.paint(260, 480, 0x58188D)
        elif (x, y) == (93, 680) and self.panel_open:  # the Ascension tab of an open panel
            self.fake.paint(260, 480, 0x58188D)
        elif (x, y) == (205, 696):
            self.fake.paint(158, 676, 0x5E261B)  # tree tab selected
        elif (x, y) == (570, 694):
            self.panel_open = False
            self.fake.frame[:] = 0  # panel closed
        elif self.modal_for is None:
            name = next((n for n, point in ORDER if point == (x, y)), None)
            if name:
                self.show(name)
        elif (x, y) == (534, 582) and not self.jewel_offer:  # Buy
            if self.modal_for in self.poor:
                self.jewel_offer = True
                self.fake.paint(468, 571, 0x094309)
                self.fake.paint(583, 521, 0xFFFFFF)
            elif self.press_ms:
                self.fake.paint(468, 571, 0x094309)  # pressed; the box at (583, 521) stays dark
                self.bought_at = self.fake.t + self.press_ms
            else:
                self.bought.add(self.modal_for)
                self.hide()
        elif (x, y) in ((648, 582), (758, 582)):  # a red modal's wide button / Close
            self.hide()

    def show(self, name: str) -> None:
        self.modal_for = name
        self.fake.paint(538, 681, 0x150202)
        if name in self.bought or name in self.locked:
            self.fake.paint(468, 571, 0xAF0000)
            if name in self.locked:  # "Can't buy yet" is about 170 px wide, "Close" 61
                self.fake.paint(561, 582, 0xFFFFFF, w=170)
        else:
            self.fake.paint(468, 571, 0x00A400)

    def hover(self, x: int, y: int) -> None:
        if self.tooltip_at:  # the old tooltip goes away
            tx, ty = self.tooltip_at
            self.fake.paint(tx + 43, ty - 30, 0, w=200, h=61)
            self.tooltip_at = None
        name = next((n for n, point in ORDER if point == (x, y)), None)
        if name is None or not self.tooltips or self.modal_for:
            return
        self.tooltip_at = (x, y)
        self.fake.paint(x + 43, y - 30, 0x262626, w=200, h=61)
        if name not in self.bought:
            poor = name in self.poor and not self.lying_tooltips
            self.fake.paint(x + 80, y + 15, 0xAD1111 if poor else 0x11AA23, w=8, h=8)  # "Cost: N"...
            self.fake.paint(x + 95, y + 15, 0x6A31CA, w=8, h=8)  # ...and the SP icon
        else:
            self.fake.paint(x + 80, y + 15, 0x11AA23, w=30, h=8)  # "Unlocked": green too, no SP icon

    def hide(self) -> None:
        self.modal_for = None
        self.jewel_offer = False
        self.fake.paint(583, 521, 0)
        self.fade_until = self.fake.t + self.FADE_MS
        self.fake.paint(538, 681, 0x3C0606)
        self.fake.paint(468, 571, 0)
        self.fake.paint(561, 582, 0, w=170)


def nodes_clicked(fake) -> list[str]:
    names = {point: name for name, point in ORDER}
    return [names[c] for c in fake.clicks() if c in names]


def name(i: int) -> str:
    return ORDER[i][0]


def test_buys_in_order_skips_bought_and_locked_nodes_and_stops_without_enough_sp(game, fake, events) -> None:
    # The wiki's order doesn't follow the tree's links: a node locked by a later prerequisite is skipped.
    tree = FakeTree(fake, bought={name(0)}, locked={name(2)}, poor={name(4)})
    Tree(game, RECOMMENDED_ORDER).buy()

    assert tree.bought == {name(0), name(1), name(3)}
    assert [r["node"] for r in events() if r["event"] == "Tree node bought"] == [name(1), name(3)]
    assert name(5) not in nodes_clicked(fake)  # stopped at name(4): wait for SP, in the wiki's order
    # The panel stays open: the runner sends the minions right after, and send_minions closes it.
    assert (570, 694) not in fake.clicks() and tree.panel_open


def test_a_locked_node_is_checked_again_only_after_a_purchase(game, fake) -> None:
    tree_ui = FakeTree(fake, locked={name(0)}, poor={name(1)})
    tree = Tree(game, RECOMMENDED_ORDER)
    tree.buy()
    fake.actions.clear()
    tree.buy()  # nothing bought since: name(0) is still locked
    assert nodes_clicked(fake) == [name(1)]

    tree_ui.poor.clear()
    tree.buy()  # buys name(1), which may have unlocked name(0)
    fake.actions.clear()
    tree.buy()
    assert nodes_clicked(fake)[:2] == [tree.bought[-1], name(0)]  # right after the memory's check


def test_zooms_all_the_way_out_before_clicking_a_node(game, fake) -> None:
    FakeTree(fake, locked={name(0)})
    Tree(game, RECOMMENDED_ORDER).buy()

    wheel_downs = [i for i, a in enumerate(fake.actions) if a == ("button", 5, True)]
    first_node = next(i for i, a in enumerate(fake.actions) if a == ("click", ORDER[0][1][0] - 8, ORDER[0][1][1] - 31))
    assert len(wheel_downs) >= 20 and wheel_downs[19] < first_node  # more follow: back from the "top" layout


def test_never_buys_a_node_whose_tooltip_shows_the_cost_in_red(game, fake, events) -> None:
    # Buy without enough SP offers to pay the difference with jewels, bought with real money (2026-10-26).
    tree = FakeTree(fake, poor={name(0)})
    Tree(game, RECOMMENDED_ORDER).buy()

    assert (534, 582) not in fake.clicks()
    assert nodes_clicked(fake) == [name(0)]  # opened only to see it isn't locked, then closed
    assert [r["reason"] for r in events() if r["event"] == "Tree stopped"] == ["not enough SP"]
    assert not tree.box_ticked


def test_never_clicks_buy_without_seeing_the_cost_in_green(game, fake, events) -> None:
    tree = FakeTree(fake, tooltips=False)
    Tree(game, RECOMMENDED_ORDER).buy()

    assert (534, 582) not in fake.clicks()
    assert (758, 582) in fake.clicks()  # the modal's Close
    assert tree.bought == set()
    assert [r["reason"] for r in events() if r["event"] == "Tree stopped"] == ["cost not read"]


def test_closes_a_jewel_offer_at_once_and_never_ticks_its_box(game, fake, event_names) -> None:
    tree = FakeTree(fake, poor={name(0)}, lying_tooltips=True)
    Tree(game, RECOMMENDED_ORDER).buy()

    assert "Tree jewel offer closed" in event_names()
    assert fake.clicks().count((534, 582)) == 1  # Buy, once
    assert fake.clicks()[fake.clicks().index((534, 582)) + 1] == (758, 582)  # then straight to Close
    assert not tree.box_ticked and tree.bought == set()


def test_a_bought_node_is_recognised_from_its_tooltip_without_opening_it(game, fake) -> None:
    # After a restart the bot checked every bought node by hovering 1.5 s and opening it (2026-10-26).
    FakeTree(fake, bought={name(0), name(1)}, poor={name(2)})
    start = fake.t
    Tree(game, RECOMMENDED_ORDER).buy()

    assert nodes_clicked(fake) == [name(2)]  # opened only to see it isn't locked
    assert fake.t - start < 5_000


def test_only_the_last_bought_node_is_checked_again_in_the_next_run(game, fake) -> None:
    FakeTree(fake, bought={name(0), name(1)}, poor={name(2)})
    tree = Tree(game, RECOMMENDED_ORDER)
    tree.buy()
    fake.actions.clear()
    tree.buy()

    assert nodes_clicked(fake) == [name(1), name(2)]  # the memory's check, then the next node
    assert [a for a in fake.actions if a[0] == "move" and (a[1] + 8, a[2] + 31) == ORDER[0][1]] == []


def test_bought_nodes_are_remembered_between_starts(game, fake, tmp_path, event_names) -> None:
    # Every Start walked the whole order again: 23 s at 10-28 02:07, against 3.6 s later in the same run.
    state = tmp_path / "state.json"
    FakeTree(fake, bought={name(0), name(1)}, poor={name(2)})
    Tree(game, RECOMMENDED_ORDER, state).buy()
    assert load_state(state)["tree_bought"] == [name(0), name(1)]

    fake.actions.clear()
    start = fake.t
    Tree(game, RECOMMENDED_ORDER, state).buy()  # the bot started again

    assert nodes_clicked(fake) == [name(1), name(2)]
    assert [a for a in fake.actions if a[0] == "move" and (a[1] + 8, a[2] + 31) == ORDER[0][1]] == []
    assert "Tree memory cleared" not in event_names()
    assert fake.t - start < 5_000


def test_an_ultra_ascension_clears_the_memory_without_buying_anything(game, fake, tmp_path, event_names) -> None:
    # An Ultra Ascension resets the tree: the last node remembered shows Buy again. Its modal is only read.
    state = tmp_path / "state.json"
    update_state(state, tree_bought=[name(0), name(1)])
    tree_ui = FakeTree(fake, poor={name(0)})  # name(1) is affordable: a Buy click would buy it
    Tree(game, RECOMMENDED_ORDER, state).buy()

    assert "Tree memory cleared" in event_names()
    assert (534, 582) not in fake.clicks() and tree_ui.bought == set()
    assert nodes_clicked(fake) == [name(1), name(0)]  # the check, then the order from its start
    assert load_state(state)["tree_bought"] == []


def test_the_memory_is_checked_on_every_run(game, fake, event_names) -> None:
    tree_ui = FakeTree(fake, bought={name(0)}, poor={name(1)})
    tree = Tree(game, RECOMMENDED_ORDER)
    tree.buy()
    tree_ui.bought.clear()  # an Ultra Ascension by hand while the bot runs
    tree_ui.poor.add(name(0))  # and no SP left for it
    tree.buy()

    assert "Tree memory cleared" in event_names()
    assert tree.bought == []


def test_names_no_longer_in_the_tree_are_dropped_from_the_memory(game, tmp_path) -> None:
    state = tmp_path / "state.json"
    update_state(state, tree_bought=["Moon Boots", name(0), 7])

    assert Tree(game, RECOMMENDED_ORDER, state).bought == [name(0)]


def test_nothing_is_clicked_in_the_tree_when_its_tab_does_not_show(game, fake, event_names) -> None:
    tree = FakeTree(fake)
    fake.on_action = lambda a: None if a == ("click", 205 - 8, 696 - 31) else tree.act(a)
    Tree(game, RECOMMENDED_ORDER).buy()

    assert nodes_clicked(fake) == []
    assert "Tree not shown" in event_names()
    assert fake.clicks()[-1] == (570, 694)


def test_tree_follows_the_given_order(game, fake) -> None:
    FakeTree(fake, bought={"Green Ore", "Portals"})
    Tree(game, ("Green Ore", "Portals", "Pink Ore")).buy()

    assert set(nodes_clicked(fake)) == {"Pink Ore"}  # the other two are bought: recognised without opening
    moves = [(a[1] + 8, a[2] + 31) for a in fake.actions if a[0] == "move"]
    green, portals, pink = (moves.index(NODES[name].point) for name in ("Green Ore", "Portals", "Pink Ore"))
    assert green < portals < pink


def test_nodes_outside_the_order_are_never_touched(game, fake) -> None:
    FakeTree(fake)
    Tree(game, ("Portals",)).buy()

    assert set(nodes_clicked(fake)) == {"Portals"}


def test_a_pressed_buy_button_is_not_a_jewel_offer(game, fake, events, event_names) -> None:
    # Live 2026-10-26 (Portal Traveler 18:47, Legendary Belt 20:04): the purchases went through, but the
    # pressed Buy button 22 ms after the click was taken for the jewel offer, so the run stopped there.
    tree = FakeTree(fake, press_ms=60)
    Tree(game, RECOMMENDED_ORDER[:2]).buy()

    assert "Tree jewel offer closed" not in event_names()
    assert (758, 582) not in fake.clicks()
    assert [r["node"] for r in events() if r["event"] == "Tree node bought"] == [name(0), name(1)]
    assert tree.bought == {name(0), name(1)}


@pytest.mark.parametrize(("frame", "offer"), [("jewel-offer", True), ("pressed-buy", False)])
def test_the_jewel_offer_on_recorded_frames(game, fake, frame: str, offer: bool) -> None:
    # jewel-offer: 02:11:05 on 2026-10-26 (Portal Traveler, 95 SP of 200); pressed-buy: 20:04:02, 49 ms after
    # Legendary Belt's Buy, a purchase that went through.
    fake.frame[:] = read_png(FIXTURES / f"{frame}.png")

    assert Tree(game, ()).jewel_offer() is offer


def test_a_locked_node_is_logged(game, fake, events) -> None:
    FakeTree(fake, locked={name(0)}, poor={name(1)})
    Tree(game, RECOMMENDED_ORDER).buy()

    assert [r["node"] for r in events() if r["event"] == "Tree node locked"] == [name(0)]


def show_tree(fake, name: str) -> None:
    """A tree tab recorded in the "top" layout (client x 0-639): "top" where it was surveyed (Linux, 2026-10-28
    21:51), "top-left-edge" panned against its left edge, "top-windows" right as surveyed and "top-windows-126"
    126 px right of it (Windows, 21:29 and 21:15)."""
    fake.frame[:, :640] = read_png(FIXTURES / f"{name}.png")


@pytest.mark.parametrize(("before", "after", "shift"), [("top", "top-left-edge", 371), ("top-left-edge", "top", -371),
                                                        ("top-windows", "top-windows-126", 126),
                                                        ("top", "top-windows", 0)])
def test_measures_how_far_the_tree_panned_on_recorded_frames(game, fake, before: str, after: str,
                                                              shift: int) -> None:
    show_tree(fake, before)
    first = links(game)
    show_tree(fake, after)

    assert pan_shift(first, links(game)) == shift


def test_no_links_measure_no_pan(game, fake) -> None:
    show_tree(fake, "top")
    first = links(game)
    fake.frame[:] = 0

    assert pan_shift(first, links(game)) is None


def test_the_top_layout_is_found_from_its_left_edge(game, fake) -> None:
    # Dragged right it rests against its left edge, 371 px right of the surveyed layout; dragged 371 px back,
    # inertia takes it 14 px further (live, 2026-10-28).
    edge, top = (read_png(FIXTURES / f"{name}.png") for name in ("top-left-edge", "top"))
    back = np.zeros_like(top)
    back[:, :-14] = top[:, 14:]
    presses: list[tuple[int, int]] = []

    def pan(action: tuple) -> None:
        if action[0] == "click":
            presses.append(action[1:])
        elif action == ("button", 1, False) and fake.pointer[0] != presses[-1][0]:  # a sideways drag
            fake.frame[:, :640] = edge if fake.pointer[0] > presses[-1][0] else back

    fake.on_action = pan
    assert Tree(game, ()).find_top_layout() == -14


def test_nodes_under_the_header_are_clicked_where_the_top_layout_was_found(game, fake, monkeypatch) -> None:
    FakeTree(fake)
    monkeypatch.setattr(Tree, "find_top_layout", lambda self: 126)
    Tree(game, ("Ancient Quests",)).buy()

    x, y = NODES["Ancient Quests"].point
    assert (x + 126, y) in fake.clicks() and (x, y) not in fake.clicks()


def test_nothing_is_clicked_in_a_top_layout_that_was_not_found(game, fake, monkeypatch, events) -> None:
    FakeTree(fake)
    monkeypatch.setattr(Tree, "find_top_layout", lambda self: None)
    Tree(game, ("Ancient Quests", "Village Key")).buy()

    assert nodes_clicked(fake) == []
    assert [(r["node"], r["reason"]) for r in events() if r["event"] == "Tree stopped"] == [
        ("Ancient Quests", "layout not found")]


def test_nodes_under_the_header_are_bought_from_the_top_layout(game, fake, monkeypatch) -> None:
    # At minimum zoom the header covers the top rows; 3 notches in and dragged to the top they show (2026-10-26).
    FakeTree(fake)
    monkeypatch.setattr(Tree, "find_top_layout", lambda self: 0)
    Tree(game, ("Ancient Quests", "Village Key")).buy()

    actions = fake.actions
    zoom_in = actions.index(("button", 4, True))
    quests = next(i for i, a in enumerate(actions) if a[0] == "click"
                  and (a[1] + OFFSET[0], a[2] + OFFSET[1]) == NODES["Ancient Quests"].point)
    key = next(i for i, a in enumerate(actions) if a[0] == "click"
               and (a[1] + OFFSET[0], a[2] + OFFSET[1]) == NODES["Village Key"].point)
    assert NODES["Ancient Quests"].layout == "top" and NODES["Village Key"].layout == "min"
    assert zoom_in < quests < key
    assert any(a == ("button", 5, True) for a in actions[quests:key])  # back to minimum zoom first


def test_every_node_point_is_clear_of_the_header_and_the_tab_bar() -> None:
    # The header holds the "Buy on Click" toggle (95, 90): a click there would make every node click a buy.
    for name, node in NODES.items():
        x, y = node.point
        assert 15 + 8 <= x <= 615 + 8 and 105 + 31 <= y <= 620 + 31, name


@pytest.mark.parametrize(("frame", "state"), [("en-bought", "bought"), ("es-bought", "bought"),
                                              ("es-locked", "locked")])
def test_a_red_modal_is_told_by_its_button_text_in_english_and_spanish(game, fake, frame: str, state: str) -> None:
    # The button's white text, 2026-10-28: "Close" 61 px wide and "Cerrar" 79; "Can't buy yet" about 170 (from
    # the font) and "No se puede comprar todavía" 370. "Cerrar" reached into the old check's strip.
    fake.frame[:] = read_png(FIXTURES / f"{frame}.png")

    assert Tree(game, ()).modal() == state


def test_a_tooltip_that_reaches_past_the_panel_is_read(game, fake) -> None:
    """Giant Horde (client 489, 301), 2026-10-30 13:36: the tooltip runs out of the panel to client x 783, past its
    edge (x 639). Read only up to that edge, its SP icon was cut off: "cost not read" for Giant Horde, Ramen and Stew
    on every tree visit that day."""
    fake.frame[200:400, 480:800] = read_png(FIXTURES / "giant-horde-tooltip.png")
    assert Tree(game, RECOMMENDED_ORDER).read_tooltip(*NODES["Giant Horde"].point) == "not enough"
