import idle_runner.minigames.chest_hunt as chest_hunt_module
from idle_runner.minigames.chest_hunt import Chest, State, chest_hunt, find_saver, process_grid, updated_state


def test_normal_strategy_opens_the_life_saver_after_the_second_chest() -> None:
    assert updated_state(0, State.NO_MIMIC, Chest.REWARD, False, False) == State.NO_MIMIC
    assert updated_state(0, State.NO_MIMIC, Chest.MIMIC, False, False) == State.ONE_MIMIC
    assert updated_state(1, State.ONE_MIMIC, Chest.REWARD, False, False) == State.OPEN_LIFE_SAVER


def test_2x_chest_always_opens_the_life_saver() -> None:
    assert updated_state(5, State.NO_MIMIC, Chest.X2, True, False) == State.OPEN_LIFE_SAVER


def test_normal_state_is_final() -> None:
    assert updated_state(3, State.NORMAL, Chest.X2, False, False) == State.NORMAL


def test_without_reinforced_crystal_saver_the_life_saver_opens_first() -> None:
    assert updated_state(0, State.NO_MIMIC, Chest.REWARD, False, True) == State.OPEN_LIFE_SAVER


def test_perfect_strategy_thresholds() -> None:
    assert updated_state(1, State.NO_MIMIC, Chest.MIMIC, True, False) == State.ONE_MIMIC
    assert updated_state(1, State.ONE_MIMIC, Chest.MIMIC, True, False) == State.TWO_MIMICS
    assert updated_state(12, State.NO_MIMIC, Chest.REWARD, True, False) == State.NO_MIMIC
    assert updated_state(13, State.NO_MIMIC, Chest.REWARD, True, False) == State.OPEN_LIFE_SAVER
    assert updated_state(15, State.ONE_MIMIC, Chest.REWARD, True, False) == State.OPEN_LIFE_SAVER
    assert updated_state(21, State.TWO_MIMICS, Chest.REWARD, True, False) == State.OPEN_LIFE_SAVER


def test_find_saver(game, fake) -> None:
    fake.paint(377, 325, 0xFFEB04)  # row 0, column 2 (x = 185 + 2 * 95)
    assert find_saver(game) == (375, 325)


def test_process_grid_skips_the_saver_and_stops_at_the_end_screen(game, fake) -> None:
    def end_after_two_clicks(action: tuple) -> None:
        if action[0] == "click" and len(fake.clicks()) == 2:
            fake.paint(550, 694, 0xAF0000)  # close button = chest hunt over

    fake.on_action = end_after_two_clicks
    process_grid(game, (280, 325), no_lockpicking=False, perfect=False, no_reinforced=False)

    assert fake.clicks() == [(218, 302), (408, 302)]  # column 1 (the saver) was skipped


def test_chest_hunt_without_saver_still_finishes(game, fake, event_names) -> None:
    fake.paint(550, 694, 0xAF0000)
    chest_hunt(game, no_lockpicking=True, perfect=False, no_reinforced=False)

    assert fake.clicks()[-1] == (643, 693)
    assert "Chesthunt saver not found" in event_names()


def test_chest_hunt_saves_start_and_end_frames(game, fake, events) -> None:
    fake.paint(550, 694, 0xAF0000)
    chest_hunt(game, no_lockpicking=False, perfect=False, no_reinforced=False)

    labels = [r["label"] for r in events() if r["event"] == "frame"]
    assert "chesthunt-start" in labels and "chesthunt-end" in labels


def test_blocked_end_screen_logs_the_original_text_and_opens_the_grid_again(game, fake, event_names,
                                                                             monkeypatch) -> None:
    grids = []

    def grid(*args: object) -> None:
        grids.append(args)
        if len(grids) == 2:
            fake.paint(550, 694, 0xAF0000)  # the second pass reaches the end screen

    monkeypatch.setattr(chest_hunt_module, "process_grid", grid)
    chest_hunt(game, no_lockpicking=False, perfect=False, no_reinforced=False)

    assert len(grids) == 2
    assert "Chsthunt  Blocked divinity  X, Start Again " in event_names()  # typos as in ChestHunt.au3:56


def test_a_perfect_hunt_bonus_is_waited_for_not_taken_for_a_blocked_grid(game, fake, event_names,
                                                                          monkeypatch) -> None:
    # 2026-11-12/16: after all 29 chests the game shows three bonus chests and opens them (~16 s from the
    # last chest to Close); the 10 s limit ran out meanwhile, so every perfect hunt logged "Blocked" and
    # clicked the grid again.
    grids = []
    monkeypatch.setattr(chest_hunt_module, "process_grid", lambda *args: grids.append(args))
    sleep = fake.sleep_ms
    start = fake.t

    def timeline(ms: float) -> None:
        sleep(ms)
        if fake.t - start > 2_000 and not fake.clicks():
            fake.paint(457, 439, 0xF68F37)  # the bonus chests show
        elif fake.clicks():
            fake.paint(457, 439, 0)
            if fake.t - start > 16_000:
                fake.paint(550, 694, 0xAF0000)  # Close, once the three are open

    monkeypatch.setattr(fake, "sleep_ms", timeline)
    chest_hunt(game, no_lockpicking=False, perfect=True, no_reinforced=False)

    assert len(grids) == 1
    assert "Chsthunt  Blocked divinity  X, Start Again " not in event_names()
    assert "Perfect ChestHunt Completed" in event_names()
