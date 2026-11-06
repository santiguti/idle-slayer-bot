from idle_runner.minigames.boss import (
    EMPTY_HEART,
    FLAME_HOLD_MS,
    FLAME_JUMP_X,
    GIVE_UP_MS,
    HEARTS,
    boss_fight_knight,
    charge_attack,
    charge_left_of_column,
    down_attack,
    flame_attack,
    flame_dodge,
    upper_attack,
    victor_battle,
)


class FakeShooter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def resume(self) -> None:
        self.calls.append("resume")

    def pause(self) -> None:
        self.calls.append("pause")


def test_victor_battle_ends_when_won(game, fake, event_names) -> None:
    fake.paint(835, 477, 0xFD3169)  # the victory screen
    shooter = FakeShooter()
    victor_battle(game, shooter)

    assert "Victor Won" in event_names()
    assert (615, 563) in fake.clicks()
    assert shooter.calls[0] == "resume" and shooter.calls[-1] == "pause"


def test_victor_battle_gives_up_in_the_end(game, fake, event_names) -> None:
    fake.cost_ms = 200
    victor_battle(game, FakeShooter())

    assert "Victor Lost" in event_names()
    assert GIVE_UP_MS < fake.t < GIVE_UP_MS + 15_000


def test_victor_battle_gives_stage_two_time_to_shoot() -> None:
    assert GIVE_UP_MS >= 400_000  # stage 1 takes ~80 s; the original's 200 s ended attempt 4 mid-fight


def test_victor_battle_ends_when_every_heart_is_empty(game, fake, event_names) -> None:
    for x, y in HEARTS:
        fake.paint(x, y, EMPTY_HEART)
    shooter = FakeShooter()
    victor_battle(game, shooter)

    assert "Victor Lost" in event_names()
    assert fake.t < 10_000  # not the 200 s timeout
    assert shooter.calls[-1] == "pause"


def test_victor_battle_fights_on_while_a_heart_is_left(game, fake, event_names) -> None:
    for x, y in HEARTS[:4]:
        fake.paint(x, y, EMPTY_HEART)
    fake.cost_ms = 200
    victor_battle(game, FakeShooter())

    assert fake.t > GIVE_UP_MS


def test_stage_two_keeps_shooting_after_the_dialog(game, fake, event_names) -> None:
    fake.paint(272, 130, 0xAE6C37)  # the stage 2 dialog
    sleep = fake.sleep_ms

    def sleep_ms(ms: float) -> None:
        sleep(ms)
        if fake.t > 9_000:
            fake.paint(272, 130, 0x000000)  # the dialog closes
        if fake.t > 30_000:
            for x, y in HEARTS:
                fake.paint(x, y, EMPTY_HEART)
    fake.sleep_ms = sleep_ms
    fake.cost_ms = 20
    shooter = FakeShooter()
    victor_battle(game, shooter)

    assert "Victor Stage 2" in event_names()
    # Arrows hurt Victor in stage 2 too (2026-11-05): the original's pause 4 s after the dialog left him at ~315.
    assert shooter.calls == ["resume", "resume", "pause"]


def test_stage_two_dodges_shoot_again_afterwards(game) -> None:
    for dodge in (down_attack, upper_attack):
        shooter = FakeShooter()
        dodge(game, shooter, first_stage=False)

        assert shooter.calls == ["resume"]


def test_flame_dodge_stops_shooting_until_the_jump_is_done(game, fake) -> None:
    fake.paint(FLAME_JUMP_X, 471, 0xE32CFF)
    shooter = FakeShooter()
    flame_dodge(game, shooter)

    assert shooter.calls == ["pause", "resume"]
    assert "Up" in fake.taps()


def test_victor_battle_does_not_log_every_miss(game, fake, logs) -> None:
    fake.cost_ms = 200
    victor_battle(game, FakeShooter())

    assert "pixel_search (919" not in (logs / "idle_runner.log").read_text(encoding="utf-8")


def paint_charge(fake, left: int, top: int, width: int = 64, height: int = 100) -> None:
    """Victor charging a comet: a white blob ~110 px tall (measured 2026-11-05)."""
    fake.paint(left, top, 0xFFFFFF, w=width, h=height)


def test_a_charge_left_of_the_column_is_found(game, fake) -> None:
    paint_charge(fake, 812, 294)  # recorded at client (804..868, 263..363): Victor teleported left

    assert charge_left_of_column(game) == (812, 343)


def test_a_charge_crossing_the_column_is_left_to_the_original_check(game, fake) -> None:
    paint_charge(fake, 880, 240)  # the comet leaving Victor at his usual place, through the column

    assert charge_left_of_column(game) is None


def test_comets_and_victors_sparkles_are_not_charges(game, fake) -> None:
    fake.paint(700, 340, 0xFFFFFF, w=70, h=34)  # a comet in flight: wide, flat
    fake.paint(820, 280, 0xFFFFFF, w=4, h=100)  # Victor's idle sparkles: thin

    assert charge_left_of_column(game) is None


def test_a_high_charge_waits_then_dodges_like_the_original(game, fake) -> None:
    shooter = FakeShooter()
    charge_attack(game, shooter, first_stage=True, charge=(812, 343))

    # The comet leaves 400 ms after the charge and flies 1.34 px/ms; the original reacts 456 ms before it
    # reaches the player (client x 300), and an upper attack then waits 730 ms.
    assert shooter.calls == ["pause", "resume"]
    assert fake.t >= 400 + (812 - 8 - 300) / 1.34 - 456 + 730


def test_a_low_charge_lets_the_shooter_jump_again_like_the_original(game, fake) -> None:
    shooter = FakeShooter()
    charge_attack(game, shooter, first_stage=True, charge=(696, 435))  # recorded at 20:59:05

    assert shooter.calls == ["pause", "resume"]  # DownAttackVictor in stage 1: Sleep(200), then shoot again
    assert fake.t >= 400 + (696 - 8 - 300) / 1.34 - 456 + 200


def test_flame_jump_waits_for_the_pillar(game, fake) -> None:
    pressed: list[float] = []
    fake.on_action = lambda a: pressed.append(fake.t) if a == ("key", "Up", True) else None
    fake.paint(FLAME_JUMP_X, 471, 0xE32CFF)  # the pillar's front, already close enough
    flame_attack(game)

    assert pressed[0] < 50


def test_flame_jump_sees_the_dark_red_pillar(game, fake) -> None:
    pressed: list[float] = []
    fake.on_action = lambda a: pressed.append(fake.t) if a == ("key", "Up", True) else None
    fake.paint(FLAME_JUMP_X, 471, 0x8E1B27)  # the other pillar: dark red, black and cyan (2026-11-05 21:21)
    flame_attack(game)

    assert pressed[0] < 50


def test_flame_jump_ignores_the_players_dark_red(game, fake) -> None:
    pressed: list[float] = []
    fake.on_action = lambda a: pressed.append(fake.t) if a == ("key", "Up", True) else None
    fake.paint(300, 471, 0x8E1B27)  # in the player's sprite too (client x ~210-300)
    flame_attack(game)

    assert pressed[0] >= 900


def test_flame_jump_holds_up_longer_than_the_original(game, fake) -> None:
    fake.paint(FLAME_JUMP_X, 471, 0xE32CFF)
    flame_attack(game)

    down = next(i for i, a in enumerate(fake.actions) if a == ("key", "Up", True))
    up = next(i for i, a in enumerate(fake.actions) if a == ("key", "Up", False))
    assert fake.actions[down + 1:up] == []  # nothing in between: one hold of FLAME_HOLD_MS
    assert FLAME_HOLD_MS > 100


def test_flame_jump_without_a_pillar_jumps_anyway(game, fake, event_names) -> None:
    pressed: list[float] = []
    fake.on_action = lambda a: pressed.append(fake.t) if a == ("key", "Up", True) else None
    fake.paint(FLAME_JUMP_X + 1, 471, 0xE32CFF)  # still too far
    flame_attack(game)

    assert pressed[0] >= 900
    assert "Victor flame jump" in event_names()


def test_knight_is_logged_but_not_fought(game, fake, event_names) -> None:
    boss_fight_knight(game)

    assert event_names() == ["Start of BossFight Knight"]
    assert fake.actions == []
