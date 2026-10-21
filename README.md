# Spell Cooldown Tracker

Icons-only cooldown, buff, totem and pet/imbue tracker for World of Warcraft: Forever, for every class, with per-class and per-spec settings and a combat-only swing timer.

## Install
Copy the `SpellCDTracker` folder into `Interface/AddOns/`, then restart the game or `/reload`. The folder keeps the name `SpellCDTracker`; only the name shown in game changed.

## Commands
- `/scdt` options, `/scdt spells` Tracked spells, `/scdt edit` move frames, `/scdt food on|off` optional food buff icon ("Well Fed", off by default; shown next to your buffs and red while missing), `/scdt minimap on|off` minimap button (follows square minimaps by itself), `/scdt debug` diagnostics

## Libraries
The minimap button is registered through the standard LibDBIcon-1.0 library (embedded in `Libs/` with LibStub, CallbackHandler-1.0 and LibDataBroker-1.1), so minimap button managers handle it like any other button. Confirmed in the live client on 20 Oct 2026 with Leatrix Plus' "Enhance minimap" (author's test).
