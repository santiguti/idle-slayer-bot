"""Buy Ascension Tree nodes in the user's order. Not in the original (user's request, 2026-10-26).

Measured 2026-10-26: the tree keeps its last pan and zoom, but at
its minimum zoom it is centred, so the routine zooms all the way out first and then finds where the tree is
(it moves when more of it shows: find_layout).
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

from idle_runner.actions import PANEL_X_RED, TAB_SELECTED, close_panel, open_ascension_tab
from idle_runner.game import Game
from idle_runner.log import event
from idle_runner.png import read_png
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
TOP_SLACK = 371  # the "top" layout pans 371 px either way from where it was surveyed (2026-10-28)
# Normalised correlation (`locate`) where the layout is: 0.49-1.00 for "min" on 17 recorded trees (old and new
# place, few or all nodes bought, some dimmed by a modal), 0.66-1.00 for "top" on 4; at most 0.06 on 26 frames
# without the tree, and 0.25 for "top" out of reach.
MATCH = 0.4


def edges(rgb: np.ndarray) -> np.ndarray:
    """How sharply the brightness changes at each pixel (one row and one column fewer than `rgb`)."""
    grey = rgb.astype(float).mean(axis=2)
    return np.abs(np.diff(grey, axis=0))[:, :-1] + np.abs(np.diff(grey, axis=1))[:-1, :]


def locate(image: np.ndarray, template: np.ndarray) -> tuple[int, int, float]:
    """Where `template` matches `image` best (both 2-D): the x, y of its top-left corner and the normalised
    correlation there (1: identical up to brightness and contrast). The correlation of every place at once
    comes from an FFT, each place's own brightness from running sums."""
    th, tw = template.shape
    h, w = image.shape
    t = template - template.mean()
    t /= max(float(np.linalg.norm(t)), 1e-9)  # a blank template matches nothing
    corr = np.fft.irfft2(np.fft.rfft2(image) * np.conj(np.fft.rfft2(t, (h, w))), (h, w))[:h - th + 1, :w - tw + 1]

    def window_sums(a: np.ndarray) -> np.ndarray:
        c = np.pad(a, ((1, 0), (1, 0))).cumsum(axis=0).cumsum(axis=1)
        return c[th:, tw:] - c[:-th, tw:] - c[th:, :-tw] + c[:-th, :-tw]

    spread = window_sums(image ** 2) - window_sums(image) ** 2 / t.size
    ncc = corr / np.sqrt(np.maximum(spread, 1e-9))
    y, x = np.unravel_index(ncc.argmax(), ncc.shape)
    return int(x), int(y), float(ncc[y, x])


# Where each layout is on screen moves when more of the tree shows (2026-11-17: no click hit a node after an
# Ultra Ascension). At minimum zoom the tree is centred: it showed 15 px left and 7 up after the Ultra Ascension
# node was bought (between 2026-10-30 and 11-04). The "top" layout rests against the tree's top edge, which
# moved up: its nodes showed 50 px lower. So each layout is found on screen (find_layout) from a piece of it,
# cut where NODES were surveyed: tree_min.png from a frame of 2026-11-17 (where the tree was then),
# tree_top.png from tests/fixtures/tree/top.png (as surveyed, 2026-10-28).
HERE = Path(__file__).parent
LAYOUTS = {  # name: (the piece's edges, its AutoIt top-left corner where surveyed, how far to look either way)
    "min": (edges(read_png(HERE / "tree_min.png")), (118, 191), 50),
    "top": (edges(read_png(HERE / "tree_top.png")), (158, 181), 100),
}


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
        # How far right and down of where it was surveyed each layout was found; None: not found.
        self.offset: dict[str, tuple[int, int] | None] = {}
        self.locked: set[str] = set()

    def buy(self) -> None:
        """Buy nodes in the order until one can't be bought. Leaves the panel open: the runner sends the minions
        right after, and send_minions closes it (reopening it at once was lost on every start, 2026-10-28)."""
        if not self.open_tree():
            close_panel(self.game)
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
        """Where the node is on screen; None in a layout that wasn't found."""
        (x, y), offset = NODES[name].point, self.offset.get(NODES[name].layout)
        return None if offset is None else (x + offset[0], y + offset[1])

    def still_bought(self, name: str) -> bool:
        """Open the node's modal and close it again, never pressing Buy: True if it shows bought (or can't be
        checked: a layout that wasn't found keeps the memory)."""
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
        """Zoom the tree to one of its two layouts (Node.layout) and find where it is (find_layout). "min": all
        the way out, where the tree is centred; dragging doesn't move it. "top": from there 3 notches in at the
        same spot, then dragged to the top edge, and it shows the rows the header covers at minimum zoom. The
        zoom keeps the tree's column under the pointer in place, so it lands sideways if the game saw the
        pointer elsewhere (126 px right once on Windows, 2026-10-28): it is panned against its left edge and
        dragged back to about where it was surveyed, 371 px left. Inertia took it 14 and 25 px past the drag
        (live, 2026-10-28): the drag is 20 px short."""
        g = self.game
        g.move(328, 411)  # over the tree
        g.wheel(up=False, notches=20)  # minimum zoom: 10 notches were already enough
        # Measured: settled 0.6 s after the wheel. The pointer stays over the tree meanwhile: moved off it at
        # once, the zoom was sometimes lost (the minimum zoom not found 3 times in 5, live 2026-11-17).
        g.sleep(600)
        if layout == "top":
            g.wheel(up=True, notches=3)
            g.sleep(600)
            for _ in range(3):  # inertia is ~30 px: the third drag ends against the top edge
                g.drag(328, 200, 328, 620)
                g.sleep(400)
            for _ in range(3):  # 420 px each: the left edge from anywhere
                g.drag(100, 400, 520, 400)
                g.sleep(400)
            g.drag(80 + TOP_SLACK, 400, 100, 400)
        self.offset[layout] = self.find_layout(layout)
        self.layout = layout

    def find_layout(self, layout: str) -> tuple[int, int] | None:
        """How far right and down of where it was surveyed the layout shows (its piece in LAYOUTS, looked for
        around its corner), or None if it doesn't within 2 s. Waits until no tooltip covers the tree (the pointer
        off it) and the tree has stopped: two equal reads 200 ms apart. It usually stops 0.6 s after the wheel,
        but once it wasn't found after 0.8 s, and it can match well where it is still moving: 5 px low at 0.3 s
        (live, 2026-11-17)."""
        g = self.game
        g.move(900, 400)
        g.sleep(800)
        piece, (x, y), slack = LAYOUTS[layout]
        h, w = piece.shape
        deadline, last = g.now() + 2000, None
        while True:
            dx, dy, match = locate(edges(g.grab(x - slack, y - slack, x + w + slack, y + h + slack)), piece)
            found = (dx - slack, dy - slack) if match >= MATCH else None
            if found is not None and found == last:
                return found
            if g.now() > deadline:
                return None
            last = found
            g.sleep(200)

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
