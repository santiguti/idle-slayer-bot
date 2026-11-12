# Changelog

Versions follow [Semantic Versioning](https://semver.org), read from the player's side: a **major** version (3.0.0)
needs something from you or drops something (a config that no longer loads, a platform), a **minor** version (2.6.0)
adds something new (a feature, a setting, a minigame the bot plays differently), and a **patch** version (2.6.1) only
fixes what was already there. From v2.6.0 on, every version below has a git tag with its name.

## v2.6.0 (2026-11-12)

### New
- **Bonus Stage 2: the reward goblins are shot with the bow.** After each section the game sends coins and a line of Soul Goblins. The bot's closing taps (one every half second, from the original) made the character hop over most of them: in one section it killed 7 of 48, all with the sword. Now, once the section's jumps are done and "Section Completed Flawlessly!" is on screen, the bot presses jump every 50 ms: the character stays in the air shooting arrows and picks up the coin rows on the way.

### Fixed
- **Random Boxes lost behind the Minions tab.** A Silver Box sends several Random Boxes in a row, and the character only gets one by jumping into it. The bot kept the Minions tab open, with the character not jumping, while a box floated by. Now no panel (minions, ascension, skill tree, game settings check) opens while a box is on screen, and a visit to the Minions tab ends as soon as a box shows up beside it; the bot comes back once the character has the box.
- **Windows: the game settings check missed three settings on every start.** On Windows the labels in the game's settings list are drawn a few pixels differently depending on how far the list is scrolled, and the list sometimes opened halfway down. The bot now scrolls it to the top, waits for it to stop moving, and reads the labels with some tolerance. Linux is unchanged.

## v2.5.0 (2026-11-06)

### New
- **The bot beats Victor.** Tested live on 2026-11-05: it won in 187 seconds with all 5 hearts left. What changed:
  - **It keeps shooting in the second stage.** The original stops shooting when Victor's second-stage dialog shows, but arrows still hurt him there, so the bot dodged everything until the timeout and did no damage.
  - **It dodges comets that Victor charges after teleporting to the left.** It now watches for the white charge-up glow anywhere in front of the character and times the dodge from where the glow is.
  - **It jumps the flame pillars when they are close, in both colours** (magenta and dark red), and holds the jump longer so the character clears them.
  - **It knows when the fight is lost** (all hearts empty) instead of waiting for the timeout. It also waits 400 seconds instead of 200 before giving up, because the second stage alone can take longer than 200.

### Fixed
- **Bonus Stage 2's second section ran out of time.** The section has a fixed timer, and the original's jumps take longer than it, because the character stands against each wall until the next timed jump. When the character is stuck against a wall, the bot now jumps at once.
- **The character stood still after Second Wind and at the start of a section.** In both cases the game waits for a key before the character runs, so the bot waited 15 seconds for a marker that never came and then jumped blind. It now presses Up when the screen stays still while it waits.
- **The first upgrade in the shop was sometimes left for a later visit.** Half a second after scrolling to the top, the list could still be bouncing, and the first row looked cut off. This happened in about 1 in 10 visits. The bot now waits for the list to settle.

## v2.4.1 (2026-11-03)

### New
- **"Buy now" button.** On the dashboard, next to Start: the running bot visits the shop at its next check (within 5 seconds), even with automatic buying off. Asked for by a tester on SteamOS.

### Fixed
- **Rage wasted when no Megahorde was there.** The bot recognised a Megahorde by one dark pixel of its "MEGA HORDE INCOMING!" text, and the Ascension and Minions panels (open or closing) and other banners have that same pixel: on Linux more than half of the rages came right after the bot closed a panel, and Rage then had its 10 minute cooldown when a real Megahorde came. The bot now checks the whole line of text, wherever it bobs to, and presses R once per Megahorde instead of about 20 times.
- **Tree nodes on the right of the tree never bought ("cost not read").** Their description pops up partly outside the panel, and the bot only read it up to the panel's edge, where the cost's SP icon was cut off. Giant Horde, Ramen and Stew stopped every tree run.
- **Bonus Stage 2 played blind after it was over.** When a section failed again after Second Wind, the stage ended without a fail screen; the bot took the section as complete, waited for the next ones and pressed their jumps in the normal run for about a minute and a half. It now sees the run's shop button and stops.
- **Minions stopped being claimed and sent once the tree's "The Chosen One" was bought.** It puts an orange Prestige button above every minion's button and makes that button shorter, and the bot only knew the tall one. It now handles both layouts and never touches the Prestige button. It also reads an SP header like "241 M available", and waits for the "N earned" text that each claim floats over the list before it reads the next button (on one visit it covered a minion that was then neither sent nor claimed).
- **The debug log only kept about two hours.** The checks the bot makes many times a second logged every miss; now only what they find is logged.

## v2.3.0 (2026-10-28)

### New
- **Takes the minions' Daily Bonus.** Once a day the Minions tab shows a free "Daily Bonus" that takes 3 hours off every mission running. The bot clicks it after sending the minions, while at least one is on a mission, so the missions it just started are shortened too; then it claims the ones the bonus finished and sends them again.

### Fixed
- **Windows: four game settings reported "not found".** The game's settings list is shorter on Windows than on Linux (no "Portrait" and other phone options), so the bot scrolled past four of them. It now reads the list a page at a time from the top until it has found all five.
- **Tree nodes under the header could be clicked in the wrong place.** For Map, Hot Desert, Ancient Quests and Portal Dominum the bot zooms the tree in, and the zoom follows the mouse pointer: if the game saw the pointer elsewhere at that moment (it happened once on Windows), the tree landed 126 px to the side and the bot clicked empty space, which stopped the tree run. The bot now measures where the tree landed and clicks there; if it can't tell, it stops without clicking.
- **A lost click on the "+2" Daily Quests button counted as taken.** The button darkens as soon as the pointer is over it, and the bot took that for the button going away. It now waits for the button to disappear and reports the click as without effect otherwise.

## v2.2.1 (2026-10-28)

### Fixed
- **Minions back from a mission went unclaimed with four or more minions.** The Minions list only shows two or three whole rows, and the bot only looked at those: a "Claim Reward" lower in the list (cut off by the tabs) was never seen. The bot now scrolls the whole list, top to bottom, waiting for it to stop bouncing at its ends before it reads a button.
- **Bonus Stage 2 got stuck in its second section without the "Protect" node.** The bot started that section when the purple slimes reached a spot, but the slimes only cover the pits once "Protect" is bought: without it the character ran into a wall until the time ran out. The bot now times the section by the pits themselves, which gives the same moment with or without the node.
- **Failed clicks right after every Bonus Stage.** The stage goes on for about 14 seconds after its last section (the reward run, "Bonus Stage Completed!"); the bot already tried to shop and check the ascension bonus meanwhile, and both failed. It now waits for the normal run first.

## v2.2.0 (2026-10-28)

**Idle Runner and the bot now speak Spanish**: the window in English or Spanish, and the game played in either language.

### New
- **Idle Runner in Spanish.** The window follows your system's language, English or Spanish; *Settings → Window → Language* changes it (it takes effect when you open Idle Runner again). In Spanish it uses the game's own words: its settings, the 161 Ascension Tree nodes (on the Tree order page and in the activity list) and names like "Súbditos", "Mega Horda" or "Etapa Bonus". Idle Runner's Settings page is "Configuración", so it isn't confused with the game's "Ajustes". The Spanish page and README now show the window in Spanish.
- **Plays with the game in Spanish.** The bot now reads the game in English or in Spanish: the game's settings ("Ajustes"), the Ascension Tree's "Cerrar" and "No se puede comprar todavía", the minions' "Realizando una Misión ..." and "Dar Misión (-1,000)" (the cost is on the button's second line in Spanish) and the Upgrades tab's "Compra todo lo disponible". Before, with the game in Spanish it didn't buy upgrades, didn't see the minions, couldn't check the settings and walked the whole tree on every run.

### Fixed
- **A lost click on the Minions tab sent no minion.** With the panel already on the Minions tab, the click right after the Ascension tab's was lost, and the tab's shade still said "Minions": the bot read the Ascension tab as the minions list. It now waits for the minions' buttons and clicks the tab again once if they don't show.
- **Wrong help for "I don't have Lockpicking 100".** The divinity makes Chest Hunt animations twice as fast (the bot waits longer at each chest without it); the help said it opened more chests. The Perfect Chest Hunts help also names the Dark Divinity right: "x2 x2".

### Changed
- The Settings page starts with a new **Window** panel (the language), and the "Ascending" panel is now called **Ascension**.
- The dashboard says "Buying upgrades and equipment…" while the bot shops (it said "Shopping…").
- The Activity page's "Statistics" and "Open logs folder" buttons moved under the list: at the window's smallest size they didn't fit beside the filters.
- `config.toml` has a new `language` setting in `[general]`: `"auto"` (the system's), `"en"` or `"es"`. Older configs load as before.
- The website and the README say the game can be in English or Spanish; the Spanish ones use the game's own Spanish words and show the window in Spanish.

## v2.1.2 (2026-10-28)

### Fixed
- **Silver boxes went unclaimed.** The bot waited for one exact shade of the button's glow, which it could miss for many minutes. It now accepts the middle of the glow.
- **False chest hunts.** A coin flying past the spot the bot watches could start a "chest hunt" in the middle of the run: about 6 minutes of clicks on empty sky, with no buying or claiming meanwhile. The bot now also looks for the first chest's dark outline, which coins don't have.

### Removed
- **The "Frame offset X/Y" settings.** They only convert the original script's coordinates to the game's picture, so they're the same on every PC, and any other value quietly broke the bot (one pixel off is enough to never see the silver box). Saved settings that still have them load as before; the values are ignored.

### Known issue
- **Bonus Stage 2 stops at its second section.** With the current version of the game the bot doesn't find the start of section 2, so that section and the rest of the stage fail. Being worked on.

## v2.1.1 (2026-10-28)

### New
- **A quicker start that says what it's doing.** A second Start on the same day spends about 3 seconds in the game's menus instead of about 30. The dashboard now says what the bot is doing ("Checking the Ascension Tree…", "Shopping…") and the activity feed shows each result: "Game settings OK", "Tree: next is Safety First, not enough SP", "Minions: not enough SP to send one".
- **The tree remembers what's bought.** Bought nodes are kept in `state.json`, next to `config.toml`, so a restart doesn't walk the whole tree again. Each run first opens the last node it remembers, without buying, and forgets them all if an Ultra Ascension reset the tree. You no longer need to restart the bot after an Ultra Ascension by hand.
- **The game's settings are checked once a day.** Once they're all right the bot doesn't open them again until the next day. **Check game settings now** on the Settings page checks them again.
- **The website and the README in Spanish.** The [project page](https://santiguti.github.io/idle-slayer-bot/) opens in Spanish for browsers set to Spanish, with an English · Español switch that remembers your pick, and there's a `README.es.md`. The window itself is still in English, for now.

### Fixed
- **The minions were missed right after the tree.** The bot clicked the Minions tab while the tree's tab was still fading out and gave up 200 ms later ("Minions tab not shown"). It now waits up to 2 seconds for the tab, and visits the tree and the minions in one opening of the ascension panel.

## v2.0.0 (2026-10-28)

**Windows is out of beta**: the same bot, tested with the real game on Windows and on Linux. Download the Windows zip or the Linux `tar.gz` below; no Python needed. Changes since v2.0.0-rc2:

### New
- **Settings that play from the start.** A new install buys every 3 minutes and ascends at a +20% CpS bonus (read every 2.5 minutes) or after 30 minutes; before, buying and ascending were off, as in the original. Settings you already saved don't change. Tree buying stays off.
- **Two extra Daily Quests every day.** Once a day, after the reset at 00:00 UTC, the bot presses the free "+2" button beside the Daily Quests header.
- **Minions are sent on their missions.** The game gives each minion its own "Send on Mission" button now, so the old "claim all / send all" clicks did nothing. The bot claims them back and sends every minion your unspent SP covers at start, after each tree run and when a mission ends, reading the cost and your SP first so the game never offers jewels.
- **The game's settings are checked at start.** The bot opens Settings, reads the options it needs (custom cursor, portal dialogue, rounded bulk, hidden locked quest rewards, scientific notation), presses Cancel and lists any wrong one as a problem. It never clicks anything else in that dialog.
- **Minion missions are timed.** The bot knows how long each mission takes (the wiki's table) and comes back for the minion when it's over. Tick the Divinities that make missions faster on the new Minions panel of the Settings page.
- **Map in the Ascension Tree.** The bot knows where Map is (150 SP), and it's in the recommended order after Dark Wizard. Land Lord, Astral Sword, Astral Blessing and Daily Silver Bonus are Astral upgrades: they only show once Astral Slayer is bought.

### Fixed
- **Ascending by % stopped reading the bonus once it got high.** From about +50% the game tags the Ascend button "Recommended" and paints the numbers gold; the bot only read white, so it never ascended until the time cap. It reads the gold numbers now.
- **A Random Box was lost while claiming quests.** The bot stopped shopping for a box, but not claiming: it now closes the shop for the box there too, and claims again later.
- **Minions ran on a false signal.** The bot took the Ascension button's glow (it glows while ascending is "Recommended") for minions coming back, opened the panel for nothing and could click into it. That signal is gone.
- **The update notice never showed on test versions.** The window couldn't read a version like "2.0.0-rc2", so the rc builds never said a newer release was out. It does now; if you have rc1 or rc2, download this one by hand.
- **Bonus Stage 1 is skipped.** Left to the jumper it never collected an orb (its jumps fall short of the orbs), and buys paused it in the middle of the stage. The bot now lets its first section run out and closes the stage, as the original does with every stage but 2 and 3.

## v2.0.0-rc2 (2026-10-27)

### New
- **Downloads on each release.** A Windows zip and a Linux `tar.gz` (with an `install.sh` that adds Idle Runner to the application menu), each with its SHA-256, built by GitHub Actions. No Python needed.

### Fixed
- The frozen executable crashed on start with "No module named idle_runner.__main__"; the release build now finds the package.

## v1.5.1 (2026-10-27)

### New
- **Support button.** The window's sidebar has a "Support Idle Runner" button, and the Help page a link, to the project's Ko-fi page.

### Fixed
- The automated tests failed on Windows: some files were read with Windows' default text encoding instead of UTF-8.

## v1.5.0 (2026-10-26)

### New
- **Tree nodes under the header.** At the tree's minimum zoom the header covers the top rows, so the bot couldn't reach them. It now zooms in and moves to the top of the tree for those nodes, a view that is also always the same. Ancient Quests and Hot Desert are back at the head of the recommended order, and Bullet Time is in it.
- **50 more tree nodes the bot knows** (surveyed in the game), from Magic Beetle Box to Portal Dominum, with their costs. They aren't in the recommended order, but you can add any of them on the Tree order page. Still not located: Map, Land Lord, Astral Sword, Astral Blessing and Daily Silver Bonus.

### Fixed
- **No clicks over another window.** If a notification or an overlay sits over the game where the bot is about to click, scroll or drag, it doesn't press the button: it pauses that action like a focus loss and keeps the moment in the black box.

## v1.4.0 (2026-10-26)

A new window, and smarter shop visits.

### New
- **A new window**, styled after Idle Slayer's own panels:
  - **Dashboard:** what the bot is doing, whether the game is found at 1280×720, this run's numbers (upgrades, ascensions, last bonus, tree nodes, problems…) and the latest events.
  - **Settings:** every option in plain words with what it does, saved as you change it. A wrong value is shown right there, by name.
  - **Tree order:** choose which Ascension Tree nodes the bot buys, and in what order. Drag them, add or remove them, search, or go back to the recommended order. Nodes bought this run are marked.
  - **Activity:** everything the bot did, filtered by purchases, ascensions, minigames or problems. Also the bot's own output, statistics and the logs folder.
  - **Help:** the game setup the bot needs, what it never does, and links.
  - It tells you when a new version is out.
- **One bot at a time.** A second bot, from the window or a terminal, stops at once with "another Idle Runner bot is already running": two bots would fight over the keys.

### Changed
- **Quest rewards are claimed in the same shop visit** as the purchases, when the Quests tab glows. A glowing shop button alone no longer starts a claim: it also glows for other things, and claims ran with nothing to claim. Each reward button is clicked once (it was clicked 2 or 3 times).
- **After an ascension the bot doesn't open the shop right away.** The game shows the shop button only with the first coins, so that buy failed every time (7 of 7 on 2026-10-26). The buy at 6 coins takes care of it.
- **Ascending at a bonus uses the panel the bonus was read from.** Closing it and opening it again right away lost the click 4 times of 7, two seconds each.
- The window stops the bot by closing its input instead of sending Ctrl+C. The bot also stops, releasing every key, if the window crashes.

### Under the hood
- A Windows backend (stdlib `ctypes`: screen capture, `SendInput`, per-monitor DPI awareness). Its input is tested on Linux with fake DLLs and its real calls on GitHub's Windows machines. It hasn't been tried with the game on Windows yet: v2.0.0 will be the release that has.

## v1.3.1 (2026-10-26)

### Fixed
- **Bonus Stage 1.** While the Ascension Tree's "Bonus Stage 2" node isn't bought (for example after an Ultra Ascension), the game shows Bonus Stage 1, which the bot didn't know. It played it with Bonus Stage 2's moves, failed at once, and kept going for about 2.5 minutes after the stage had ended, pressing the jump key in the normal run with the jumper paused. It now recognises Bonus Stage 1 on its start screen, swipes, lets the jumper play it and takes Second Wind once. With `skip_bonus_stage` it waits the stage out, as before.
- **Tree purchases taken for a jewel offer.** Twice on 2026-10-26 a node bought with Slayer Points was taken for the offer to pay with jewels, because the pressed Buy button briefly has the jewel button's colour. Nothing was spent, but the run stopped there and the purchase wasn't logged. The bot now needs both the jewel button and the offer's "I understand" box, seen twice 0.1 s apart. It also keeps watching long enough for an offer that shows late.

### Changed
- A jewel offer that does show now keeps a black-box mark, and nodes skipped because a prerequisite is missing are logged as "Tree node locked".

## v1.3.0 (2026-10-26)

Groundwork for the Windows version. Nothing changes in how the bot plays.

### New
- **`idle-runner` command.** After `pipx install` (or `pip install -e .`) the bot is the `idle-runner` command. With no arguments it opens the window, and `idle-runner --version` prints the version.

### Changed
- The package is now called `idle-slayer-bot`, the name the repository will get on GitHub. The version comes from `idle_runner.__version__`.

### Under the hood
- The game window is opened through `open_backend()`, which will pick X11 or Windows. `python-xlib` is only installed on Linux. There is no Windows backend yet.
- A build made with PyInstaller works from its own folder, where it keeps `config.toml` and `logs/`.
- Automated tests run on GitHub for Linux and Windows, with Python 3.12 and 3.14.
- A release workflow that builds the Windows zip. It runs from the v2.0.0 tag on, so v1.x tags stay Linux source releases.
- An update check against the latest GitHub release. The window doesn't use it yet.

## v1.2.1 (2026-10-26)

### Fixed
- **Coin counter after an Ultra Ascension.** The counter shows thousands with a comma ("1,251"). The bot read them as small numbers (7.0) and announced "Coins reached 6" about every 10 minutes. It now reads the comma and the digit 9, which it had never seen. Re-reading 3,600 recorded frames changed only the readings that used to fail.
- **"Swipe to Start" in bonus stages.** If the swipe didn't take, the bot was supposed to try again, but it waited for a white pixel this version of the game never shows. It now swipes again while the green handle is still showing in any of its four places (seen in all 30 recorded stage starts).
- **A shop that doesn't open is tried again 15 seconds later**, for example right after a minigame, while its results screen still covers the shop. Before, the bot waited for the next buy interval. It retries once: if the shop stays shut, the normal interval takes over again.

## v1.2.0 (2026-10-26)

### New
- **Choose which Ascension Tree nodes the bot buys, and in what order.** List them under `tree_order` in a new `[tree]` section of `config.toml`. A name the bot doesn't know, or a name listed twice, is reported as an error. Without the list the bot uses the recommended order: 110 nodes, now including the first ones (Village Key, Idle Earrings I and II, Blessing of Cronus, Portals, the ores and Soul Gem) for players who haven't bought them yet. Saving settings from the window keeps your list.
- **Orange Random Box.** The box with a sword is now seen like the silver one, so a buy stops for it and the jumper can grab it. It shows up often and in every zone: in 19,181 recorded frames, at 126 different minutes. Its colour appears in only one other place, the Ascension Tree panel, where the bot never looks for boxes.

## v1.1.2 (2026-10-26)

### Fixed
- **Slow check of nodes already bought.** After each restart the bot went over every bought node: it hovered over each one for 1.5 seconds and opened it. It now recognises "Unlocked" in the tooltip and moves on in under a second, without opening the node. Checked on 34 recorded tooltips, all read right.

## v1.1.1 (2026-10-26)

A safety fix for Ascension Tree buying, which is now seen working live.

### Fixed
- **Jewel offer when Slayer Points weren't enough.**
  - Pressing Buy on a node you can't afford doesn't just fail. The game offers to cover the difference with jewels, which are bought with real money.
  - The bot pressed Buy on Portal Traveler (200 SP, with 95 available) and that offer showed. Nothing was spent: its jewel button works only after you tick "I understand", and the bot never clicks that box.
  - Now the bot hovers over each node first and presses Buy only when the tooltip shows the cost in green (enough SP).
  - With the cost in red, it stops there without opening the node. If it can't read the cost, it closes the node without buying. If a jewel offer still shows up, the bot presses only its Close.
- **Tree buying stopped after the first node.** After a purchase the bot clicks the node again to check it was bought. That click came while the node's window was still fading out, so the game ignored it and the bot stopped. It now waits for the fade to finish.

### Seen working live
- Ascension Tree buying: 7 nodes in order in 13 seconds (Idle Earrings I and II, Blessing of Cronus, Portals, Green Ore, Pink Ore, Soul Gem). It stopped at the first one it couldn't afford.

Covered by automated tests (210 of them), including one where the tooltip says there is enough SP and the game opens the jewel offer anyway.

## v1.1.0 (2026-10-26)

Idle Runner for Linux is now its own project. This release teaches it to ascend at the right moment, to spend Slayer Points on the Ascension Tree, and to keep working after an Ultra Ascension.

### New
- **Ascend by percentage.** Every `ascend_bonus_sample_minutes` the bot reads the Ascend button's "+X% CpS bonus" and logs it. With `auto_ascend_percent` set, it ascends at the first reading that reaches it, and `auto_ascend_minutes` stays as the upper limit. A bonus it can't read is logged with a screenshot, never guessed.
- **Ascension Tree buying** (`auto_buy_tree`, off by default). Buys nodes in the order listed in `idle_runner/tree.py`, at start and after every ascension, the bot's or yours. It skips nodes already bought and stops at the first one it can't buy.
- The ascension panel is opened with a check: the bot waits for the Ascend button and clicks again if the first click was lost.
- The black box also keeps the moments around an unreadable ascend bonus and a tree node that wasn't bought.

### Fixed
- **No buys for almost an hour.** Closing the shop twice in a row, while it was still closing, left an empty dark panel over it that blocked every click. The bot now closes the shop only while it shows, and waits for it to finish.
- **Jewels shop opened by mistake.** After an Ultra Ascension the shop has no Quests tab, and claiming quests clicked the Jewels shop instead. The bot now checks that the Quests tab is there first.
- The Upgrades tab is recognised in both shop layouts (with and without the Quests tab).
- **Ascend by percentage never ascended.** The click that opened the ascension panel came right after the bonus reading closed it, and was lost.
- **Minion claims landing in the Ascension Tree.** After an Ultra Ascension there is no Minions tab, but the bot still clicked where the claim buttons used to be. It now claims only when the Minions tab shows.

### Everything that works
Verified live on Fedora 44 with KDE Plasma 6 (Wayland, game on XWayland) and the native Linux build of Idle Slayer:
- Jumping and boosting nonstop, at the rate you choose.
- Silver boxes, rage at Megahordes (with or without Soul Bonus) and rage during Soul Bonus.
- Buying upgrades and equipment, including the first round of equipment. The Vertical Magnet and Special Vertical Magnet are never bought, and blue event-quest rows are bought only once claimed.
- Stopping a purchase for a floating Random Box so the jumper can grab it, then buying again.
- Buying as soon as the counter shows 6 coins after an ascension (the bot's or yours), then waiting longer between buys until `auto_buy_minutes`.
- Claiming quest rewards.
- Collecting minions and the daily bonus (before an Ultra Ascension).
- Chest hunts, including the life saver.
- Bonus Stage 2, including Second Wind.
- Ascending on a timer and by percentage (on 2026-10-26 it ascended at +12.1% with a 10% target). Every bonus reading since 2026-10-25 was readable.
- Pausing when the game loses focus or the window isn't 1280x720, and resuming afterwards. Finding the game again after it is closed and restarted.
- Logging errors and stuck screens with a screenshot and carrying on.
- The black box, **Mark problem** and the settings window.

Covered by automated tests (208 of them), not yet seen live:
- Ascension Tree buying.
- Ascending while both the Ascend and Ultra Ascend buttons show: every automatic ascension so far happened with the single button shown right after an Ultra Ascension.
- The minion fix above (the Minions node isn't bought again yet).
- Portals, Ascending Heights, the Victor boss fight and crafting (Souls Compass, Rage Pill, Dimensional and Bidimensional staffs).

### Known limitations
- Bonus Stage 2 can still fall out of step in some sections (`Sync timeout` in the log); it carries on and finishes the stage.
- The tree order lives in `idle_runner/tree.py`, not in the settings window. Restart the bot after an Ultra Ascension done by hand.
- Linux only (X11 or XWayland). The Knight boss fight stays disabled.

## v0.1.0 (2026-10-23)

First public release: a Linux port of [Devil4ngle's Idle Runner](https://github.com/Devil4ngle/Idle_Slayer_Script) for the native Linux build of Idle Slayer.

### Same as the original
- Jumps and boosts, collects silver boxes, rages at Megahordes, takes portals, buys upgrades and equipment, claims quest rewards, collects minions and can ascend on a timer.
- Plays chest hunts, bonus stages, Ascending Heights and the Victor boss fight.
- Uses the original's coordinates, colours and timings, so it behaves the same way.

### Better than the original
- No blind spots: the original paused 2 seconds out of every 5, so 40% of the time it couldn't see Megahordes, chest hunts, quests or silver boxes. That pause is gone.
- Safe auto-ascend: it can no longer hit the new **Ultra Ascend** button by accident.
- Easier to control: it plays while the game is focused and pauses as soon as you switch windows. No hotkeys and no focus stealing.
- Recovers on its own: unexpected errors and stuck loops are logged and skipped instead of freezing the bot.
- Black box recorder: it keeps the last hour of gameplay, so you can see exactly what happened while you were away.
- Faster buying right after an ascension.
- Small window with Start/Stop, settings and a **Mark problem** button.

### Known limitations
- Linux only (X11 or XWayland). On Windows, use the original.
- The Knight boss fight stays disabled, as in the original.
