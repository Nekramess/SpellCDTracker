# Changelog

Dates are when the change landed on `main` (from git history). Versions before 0.11.0 are from the project notes, not git history.

## 0.14.1 (20 Oct 2026)
- The minimap button now uses the standard LibDBIcon library (embedded in `Libs/`), so minimap button managers such as Leatrix Plus handle it like a normal button instead of calling it a custom button. Confirmed in the live client.
- Your saved button position and hidden setting carry over. `/scdt minimap on|off` shows or hides it; the square/round/auto options are gone because the library follows square minimaps by itself.
- The AddOn List shows the addon's own icon instead of a "?".

## 0.14.0 (15 Oct 2026)
- Combo point tracker for Rogue and Druid (cat form): pips, with a bar fallback if the game hides the value in combat.
- Resource bar for Rogue (energy), Warrior (rage) and Druid (by form), shown in combat.
- Pinned energy and rage abilities show their cost, light up when castable, and show the cost in red when short. Mana abilities keep the gray look.
- New "Combo points" and "Resource bar" toggles per class and spec in Tracked spells; both movable with `/scdt edit` and reset by "Reset positions".
- Fix: the buff row could not be dragged in Edit mode on any class except Paladin.
- Fix: Rogues no longer get an off-hand warning until they can dual wield (they cannot use a shield). Uses the game's `CanDualWield()`; `/scdt debug` shows the value.
- Tests: 726 checks, with mutation checks for every new behavior.

## 0.13.1 (15 Oct 2026)
- Wand shots no longer make every spell look like it is on cooldown in combat.
- No cooldown icon for Shoot.
- `/scdt debug <spell>` prints the game's raw cooldown fields.

## 0.13.0 (7 Oct 2026)
- Optional food buff icon ("Well Fed"), off by default, red while missing. `/scdt food on|off`.
- Paladin panel: all Auras in one icon (Devotion Aura by default).
- The current release zip is stored in `releases/` and checked in CI.

## 0.12.2 (6 Oct 2026)
- Uses Forever's spec and off-hand APIs.
- Added the test suite and CI.

## 0.12.1 and 0.11.1 (5 Oct 2026)
- Minimap button follows square minimaps. `/scdt minimap on|off|square|round|auto`.

## 0.12.0 (2 Oct 2026)
- Gear warnings: icon when a weapon slot is empty (off hand for Paladin, Warrior, Shaman, Rogue; ranged for Hunter). Toggle per class and spec.

## 0.11.0 (2 Oct 2026)
- Pinned "show when ready" abilities: shown grayed out in combat while off cooldown (Judgement and Holy Strike pinned by default for Paladin).

## 0.10.4
- `## Interface: 16001`, the number the Forever beta client reports.

## 0.10.2
- Weapon imbue detection fixed with aura and cast-event fallbacks (confirmed in game by Anthony).
