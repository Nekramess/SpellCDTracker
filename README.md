# Spell Cooldown Tracker

Icons-only cooldown, buff, totem and pet/imbue tracker for World of Warcraft: Forever, for every class, with per-class and per-spec settings and a combat-only swing timer.

## Rogue, Druid and Warrior
- **Combo points** (Rogue; Druid in cat form): a row of pips, shown in combat or while you hold points.
- **Resource bar** (Rogue energy, Warrior rage, Druid by form): shown in combat.
- **Cost-aware icons**: pin an energy or rage ability in Tracked spells. Its icon shows the cost, lights up when you can cast it now, and shows the cost in red when you are short.
- Both can be switched off per class and spec in Tracked spells, and moved with `/scdt edit`.

## Install
Copy the `SpellCDTracker` folder into `Interface/AddOns/`, then restart the game or `/reload`. The folder keeps the name `SpellCDTracker`; only the name shown in game changed.

## Commands
- `/scdt` options, `/scdt spells` Tracked spells, `/scdt edit` move frames, `/scdt food on|off` optional food buff icon ("Well Fed", off by default; shown next to your buffs and red while missing), `/scdt minimap on|off` minimap button (follows square minimaps by itself), `/scdt debug` diagnostics

## Libraries
The minimap button is registered through the standard LibDBIcon-1.0 library (embedded in `Libs/` with LibStub, CallbackHandler-1.0 and LibDataBroker-1.1), so minimap button managers handle it like any other button. Confirmed in the live client on 20 Oct 2026 with Leatrix Plus' "Enhance minimap" (author's test).
