"""Buy Ascension Tree nodes in the user's order. Not in the original (user's request, 2026-10-26).

Measured 2026-10-26: the tree keeps its last pan and zoom, but at
its minimum zoom every node is always at the same place, so the routine zooms all the way out first.
Clicking a node ("Buy on Click" off) opens a modal whose pixel at (468, 571) tells its state: green = Buy
(the prerequisites are met, not necessarily the SP), red = one wide button, "Can't buy yet" (a
prerequisite is missing) or "Close" (bought); the wider text tells them apart, in English and Spanish.

The order is `Settings.tree_order` (by default the wiki's, see tree_nodes.py), which doesn't follow the
tree's links: a node whose prerequisite comes later is skipped until a purchase may have unlocked it. A
node that can be bought but costs more SP than there is stops the routine, so SP is saved in that order.

**Buy without enough SP offers to pay the difference with jewels**, bought with real money (2026-10-26).
So Buy is clicked only after the node's tooltip showed its cost in green (enough SP), and that offer is
closed at once if it shows anyway. Its jewel button needs its "I understand" box ticked first; nothing in
the bot clicks that box.

The nodes seen bought are remembered in state.json between starts (2026-10-28: a Start walked the whole
order again, 23 s). Every run first opens the last one remembered, read-only: an Ultra Ascension resets the
tree, and then that node shows Buy again and the memory is dropped.
"""
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from idle_runner.actions import PANEL_X_RED, TAB_SELECTED, open_ascension_tab
from idle_runner.game import Game
from idle_runner.log import event
from idle_runner.state import load_state, update_state
from idle_runner.tree_nodes import NODES

MODAL_STATE = (468, 571)
BUY_GREEN = 0x00A400
MODAL_RED = 0xAF0000
LOCKED_TEXT_WIDTH = 120  # px: the red modal's button text is "Can't buy yet" when wider, "Close" when not
JEWEL_BUTTON = 0x094309  # at MODAL_STATE in the jewel offer; its box at (583, 521) is white (2026-10-26)
# A node's tooltip (measured 2026-10-25/26 on 34 tooltips, all read right): a 262626 box from x + 43,
# centred on the pointer, up to ±122 px tall. Its cost line ends with the SP icon (6A31CA) and the digits
# are 11AA23 with enough SP, AD1111 without. A bought node's says "Unlocked", 11AA23 on a row without it.
TOOLTIP_BG = (0x26, 0x26, 0x26)
SP_ICON = (0x6A, 0x31, 0xCA)
COST_GREEN = (0x11, 0xAA, 0x23)
COST_RED = (0xAD, 0x11, 0x11)
LINK = (0xDA, 0x00, 0xAE)  # the links between nodes (2026-10-28)
TOP_SLACK = 371  # the "top" layout pans 371 px either way from where it was surveyed (2026-10-28)


def links(game: Game) -> np.ndarray:
    """How many link pixels each column of the tree shows (client x 16-619, under the header)."""
    return (game.grab(24, 136, 627, 650) == LINK).all(axis=2).sum(axis=0)


def pan_shift(before: np.ndarray, after: np.ndarray) -> int | None:
    """How far right the tree moved between two `links` profiles; None if no shift makes them match. At the
    right shift they matched 0.91-0.96 on six recorded pairs (2026-10-28)."""
    n, best, best_score = len(before), None, 0.8
    for shift in range(-450, 451):  # at least 154 columns in common
        a, b = (before[:n - shift], after[shift:]) if shift >= 0 else (before[-shift:], after[:n + shift])
        score = np.minimum(a, b).sum() / max(1, np.maximum(a, b).sum())
        if score > best_score:
            best, best_score = shift, score
    return best


class Tree:
    def __init__(self, game: Game, order: Sequence[str], state: Path | None = None) -> None:
        self.game = game
        self.order = order  # node names from tree_nodes.NODES (Settings.tree_order)
        self.state = state  # state.json, where `bought` is kept between starts
        # Nodes seen bought, in that order, so they aren't clicked again. Names no longer in NODES are dropped.
        remembered = load_state(state).get("tree_bought")
        self.bought: list[str] = [n for n in remembered if isinstance(n, str) and n in NODES] \
            if isinstance(remembered, list) else []
        # Nodes seen locked ("Can't buy yet") since the last purchase: only a purchase unlocks a node.
        self.layout = "min"  # the tree's zoom (Node.layout), set by show_layout
        self.top_dx: int | None = None  # how far right of its surveyed place the "top" layout is; None: not found
        self.locked: set[str] = set()

    def buy(self) -> None:
        """Buy nodes in the order until one can't be bought. Leaves the panel open: the runner sends the minions
        right after, and send_minions closes it (reopening it at once was lost on every start, 2026-10-28)."""
        if not self.open_tree():
            self.game.click(570, 694)  # close the panel (its X tab, as CollectMinion does)
            return
        if self.bought and not self.still_bought(self.bought[-1]):
            event("Tree memory cleared", node=self.bought[-1])
            self.bought.clear()
        for name in self.order:
            if name in self.bought or name in self.locked:
                continue
            node = NODES[name]
            if node.layout != self.layout:
                self.show_layout(node.layout)
            if (point := self.point(name)) is None:
                event("Tree stopped", node=name, reason="layout not found")
                self.game.save_frame("tree-layout-not-found")
                break
            if not self.buy_node(name, point):
                break
        update_state(self.state, tree_bought=self.bought)

    def point(self, name: str) -> tuple[int, int] | None:
        """Where the node is in the layout on screen; None in a "top" layout that wasn't found."""
        node = NODES[name]
        if node.layout != "top":
            return node.point
        return None if self.top_dx is None else (node.point[0] + self.top_dx, node.point[1])

    def still_bought(self, name: str) -> bool:
        """Open the node's modal and close it again, never pressing Buy: True if it shows bought (or can't be
        checked: a "top" layout that wasn't found keeps the memory)."""
        node = NODES[name]
        if node.layout != self.layout:
            self.show_layout(node.layout)
        if (point := self.point(name)) is None:
            return True
        state = self.open_modal(point)
        if state == "buy":
            self.close_modal(758, 582)  # Close
        elif state:
            self.close_modal(648, 582)  # the wide "Close" / "Can't buy yet"
        return state == "bought"

    def show_layout(self, layout: str) -> None:
        """Zoom the tree to one of its two layouts (Node.layout). "min": all the way out, where every node
        has a fixed place (2026-10-26). "top": from there 3 notches in at the same spot, then dragged to the top
        edge, and it shows the rows the header covers at minimum zoom. Its height is fixed, its sideways place
        is measured (find_top_layout). Dragging doesn't move the tree at minimum zoom."""
        g = self.game
        g.move(328, 411)  # over the tree
        g.wheel(up=False, notches=20)  # minimum zoom: 10 notches were already enough
        g.sleep(600)  # measured: settled 0.6 s after the wheel
        if layout == "top":
            g.wheel(up=True, notches=3)
            g.sleep(600)
            for _ in range(3):  # inertia is ~30 px: the third drag ends against the top edge
                g.drag(328, 200, 328, 620)
                g.sleep(400)
            self.top_dx = self.find_top_layout()
        self.layout = layout

    def find_top_layout(self) -> int | None:
        """How far right of its surveyed place the "top" layout is, or None. The zoom keeps the tree's column
        under the pointer in place, so the layout lands sideways if the game saw the pointer elsewhere: 126 px
        right once on Windows (2026-10-28), and the click on Ancient Quests hit empty space. Its left edge is a
        fixed place, 371 px right of the surveyed layout: pan the tree there, drag it back and measure where
        it came to rest. Inertia took it 14 and 25 px past the drag (live, 2026-10-28): the drag is 20 px short."""
        g = self.game
        for _ in range(3):  # 420 px each: the left edge from anywhere
            g.drag(100, 400, 520, 400)
            g.sleep(400)
        edge = self.links_at_rest()
        g.drag(80 + TOP_SLACK, 400, 100, 400)
        moved = pan_shift(edge, self.links_at_rest())
        return None if moved is None else TOP_SLACK + moved

    def links_at_rest(self) -> np.ndarray:
        """`links` once the tree has stopped and no tooltip covers it (the pointer off the tree)."""
        self.game.move(900, 400)
        self.game.sleep(800)
        return links(self.game)

    def open_tree(self) -> bool:
        g = self.game
        if open_ascension_tab(g):
            g.click(205, 696)  # tree tab
            deadline = g.now() + 2000
            while g.now() <= deadline:
                if g.pixel_search(158, 676, 158, 676, TAB_SELECTED, variation=6):
                    self.show_layout("min")
                    return True
                g.sleep(10)
        event("Tree not shown")
        g.save_frame("tree-not-shown")
        return False

    def buy_node(self, name: str, point: tuple[int, int]) -> bool:
        """Buy one node if it isn't bought yet. False when the routine must stop here."""
        g = self.game
        tooltip = self.tooltip(point)
        if tooltip == "unlocked":
            self.bought.append(name)
            return True
        state = self.open_modal(point)
        if state == "bought":
            self.bought.append(name)
            return self.close_modal(648, 582)  # its wide "Close" button
        if state == "locked":  # a prerequisite comes later in the wiki's order: go on
            self.locked.add(name)
            event("Tree node locked", node=name)
            return self.close_modal(648, 582)  # "Can't buy yet"
        if state != "buy":
            event("Tree stopped", node=name, reason="no modal")
            g.save_frame("tree-stopped")
            return False
        if tooltip == "not enough":  # wait for the SP, in the wiki's order
            event("Tree stopped", node=name, reason="not enough SP")
            self.close_modal(758, 582)  # Close
            return False
        if tooltip != "enough":  # the tooltip's cost wasn't read: never Buy blind
            event("Tree stopped", node=name, reason="cost not read")
            g.save_frame("tree-cost-not-read")
            self.close_modal(758, 582)  # Close
            return False
        g.click(534, 582)  # Buy
        if self.jewel_offer_closed(name):
            return False
        if self.wait_modal_gone() and self.open_modal(point) == "bought":  # check it took
            self.bought.append(name)
            self.locked.clear()  # it may have unlocked nodes earlier in the order
            event("Tree node bought", node=name)
            return self.close_modal(648, 582)
        event("Tree node not bought", node=name)  # not enough SP, most likely
        g.save_frame("tree-not-bought")
        state = self.modal()
        if state == "buy":
            self.close_modal(758, 582)  # Close
        elif state:
            self.close_modal(648, 582)
        return False

    def tooltip(self, point: tuple[int, int]) -> str | None:
        """Hover the node and read its tooltip: "enough" (cost in green), "not enough" (in red), "unlocked"
        (bought), or None if none of them shows within 1.5 s. Two equal reads 100 ms apart (it fades in)."""
        g = self.game
        x, y = point
        g.move(x, y)
        g.sleep(200)  # the previous node's tooltip goes; this one needs ~0.5 s of hovering
        deadline = g.now() + 1500
        while g.now() <= deadline:
            state = self.read_tooltip(x, y)
            if state:
                g.sleep(100)
                if self.read_tooltip(x, y) == state:
                    return state
            g.sleep(50)
        return None

    def read_tooltip(self, x: int, y: int) -> str | None:
        # y 31 and 750: the client area's top and bottom. The tooltip may run out of the panel (Giant Horde's reaches
        # client x 783, 2026-10-30): cut at the panel's edge (x 647), its SP icon was lost and the cost never read.
        region = self.game.grab(x + 43, max(y - 170, 31), x + 343, min(y + 170, 750))
        background = (region == TOOLTIP_BG).all(axis=2)
        if not background.any():
            return None
        ys, xs = np.nonzero(background)
        box = region[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        icon_rows = (box == SP_ICON).all(axis=2).any(axis=1)
        green_rows = (box == COST_GREEN).all(axis=2).any(axis=1)
        if (green_rows & icon_rows).any():
            return "enough"
        if ((box == COST_RED).all(axis=2).any(axis=1) & icon_rows).any():
            return "not enough"
        if (green_rows & ~icon_rows).any():
            return "unlocked"
        return None

    def jewel_offer(self) -> bool:
        """The offer to pay the missing SP with jewels: its jewel button and its unticked "I understand" box
        both show (live 2026-10-26, steady for over 0.7 s). A purchase that goes through shows the pressed Buy
        button in the jewel button's colour for a moment, but never the white box (live 18:47 and 20:04)."""
        g = self.game
        return g.pixel_is(*MODAL_STATE, JEWEL_BUTTON) and g.pixel_is(583, 521, 0xFFFFFF)

    def jewel_offer_closed(self, name: str) -> bool:
        """After Buy: if the jewel offer shows within 1 s (two equal reads 100 ms apart), click its Close
        (never its box or its jewel button) and return True. False once no modal dims the panel (the
        purchase went through) or after 1 s. The pressed Buy button is neither green nor red, so "no modal"
        can't be read from MODAL_STATE here: it ended this wait early, before a late offer could show."""
        g = self.game
        deadline = g.now() + 1000
        while g.now() <= deadline:
            if self.jewel_offer():
                g.sleep(100)
                if self.jewel_offer():
                    g.click(758, 582)  # Close
                    event("Tree jewel offer closed", node=name)
                    g.save_frame("tree-jewel-offer")
                    self.wait_modal_gone()
                    return True
            elif g.pixel_is(538, 681, PANEL_X_RED):
                return False
            g.sleep(10)
        return False

    def modal(self) -> str | None:
        """"buy", "locked", "bought", or None when no modal shows."""
        g = self.game
        if g.pixel_is(*MODAL_STATE, BUY_GREEN):
            return "buy"
        if g.pixel_is(*MODAL_STATE, MODAL_RED):
            # The button's white text, measured 2026-10-28: "Close" 61 px wide, "Cerrar" 79; "Can't buy yet"
            # about 170 (from the font's letters), "No se puede comprar todavía" 370.
            columns = np.nonzero((g.grab(428, 576, 868, 588) > 200).all(axis=2).any(axis=0))[0]
            width = int(columns[-1] - columns[0] + 1) if len(columns) else 0
            return "locked" if width > LOCKED_TEXT_WIDTH else "bought"
        return None

    def open_modal(self, point: tuple[int, int]) -> str | None:
        """Click a node and wait up to 2 s for its modal; two equal reads 100 ms apart (it opens animated)."""
        g = self.game
        g.click(*point)
        deadline = g.now() + 2000
        while g.now() <= deadline:
            state = self.modal()
            if state:
                g.sleep(100)
                if self.modal() == state:
                    return state
            g.sleep(10)
        return None

    def wait_modal_gone(self) -> bool:
        """Wait up to 2 s until the modal is gone and the panel's dimming has faded out: its X tab is
        AD1111 again (150202 under the modal, 3C0606 while it fades). A click meanwhile is lost: live on
        2026-10-26, the check 222 ms after Village Key's Buy."""
        g = self.game
        deadline = g.now() + 2000
        while g.now() <= deadline:
            if self.modal() is None and g.pixel_is(538, 681, PANEL_X_RED):
                return True
            g.sleep(10)
        return False

    def close_modal(self, x: int, y: int) -> bool:
        self.game.click(x, y)
        return self.wait_modal_gone()
