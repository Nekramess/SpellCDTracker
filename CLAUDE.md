# Spell Cooldown Tracker: notes for Claude sessions

World of Warcraft: Forever addon (Lua 5.1, one file). Shows icons only when needed: spells on cooldown, active or missing buffs, Shaman totems, weapon imbues and poisons, pet reminders, and a Paladin panel for Seal, Aura, Blessing and Righteous Fury. It also hides Forever's built-in swing timer out of combat.

Owner: Anthony (GitHub `Nekramess`). He values verified facts over confident guesses: say what is confirmed, what isn't, and where a fact came from.

These notes were written on 1 Oct 2026 from reading the code, not from in-game testing.

## Current state (keep this section up to date)

- Version 0.10.4, `## Interface: 16001` (the number the Forever beta client reports; Anthony checked it in-game on 30 Sep 2026 with `/run print(select(4, GetBuildInfo()))`).
- Published on CurseForge (listed as "Spell CD Tracker" when last seen). Plan: rename the CurseForge project to "Spell Cooldown Tracker" and start the summary with "cooldown" for search. Ask Anthony whether that's done.

## Naming rule

The name players see is **Spell Cooldown Tracker**: `## Title`, options window title, minimap tooltip, chat messages, error prefix, README title. Everything internal stays **SpellCDTracker** on purpose, so existing installs and settings carry over: folder, `.toc` file name, `SpellCDTrackerDB`, frame names (`SpellCDTrackerCDFrame` etc.), `/scdt`, and the zip name `SpellCDTracker-v<Version>-forever.zip`. Don't rename internal names without asking: it breaks installs and wipes settings.

## Files

| File | What it holds |
|---|---|
| `SpellCDTracker.toc` | Interface, Title, Version, `SavedVariables: SpellCDTrackerDB`, lists `SpellCDTracker.lua` |
| `SpellCDTracker.lua` | The whole addon (about 1,800 lines) |
| `tools/package.sh` | Builds `SpellCDTracker-v<Version>-forever.zip` from the `.toc` |
| `.github/workflows/package.yml` | Builds the zip and creates a GitHub Release |
| `docs/logo.png` | CurseForge logo |

## How SpellCDTracker.lua is organized

Top to bottom (find by function name; line numbers drift):
- Header comments, `defaults` (settings with their default values), `PALADIN_AURAS`, `Guard()`.
- Per class/spec profiles: `ProfileFor`, `RefreshProfile`. `db.profiles["CLASS"]` is "All specs"; `db.profiles["CLASS:<n>"]` exists only once a spec is customized. Profiles hold the ignore list and Paladin panel toggles.
- Icons and frames: `CreateIcon`, `MakeMovable`, `ApplyPosition`, `SetEditMode`.
- Cooldown row: `ScanSpells` (spellbook -> `known`), `UpdateCooldowns`, `UpdateGCDFlags`. `MIN_CD = 2` hides anything at or under the global cooldown.
- Paladin panel: `BuildPaladin`, `UpdatePaladin`, `RefreshPaladinFromAuras`, `OnPlayerCast`.
- Buff rows: `BUFF_GROUPS[class]` (entries made with `G(key, maintain, spells...)`; `maintain = true` shows a missing-buff reminder), imbues (Shaman), poisons (Rogue), pet summons (Hunter, Warlock), Shaman totems (`ReadTotems`), `UpdateBuffs`.
- Swing timer: `UpdateSwingTimer` (Forever's built-in bars, combat-only when `db.swingCombatOnly`).
- Tracked spells window (class icons, spec tabs, ignore toggles): `BuildSpells`, `RefreshSpells`.
- Options window: `BuildOptions` (Cooldown icon size, Paladin icon size, Text size %, Swing timer only in combat, Hide minimap button). Minimap button: `BuildMinimapButton`.
- `Debug`, the event driver (`ADDON_LOADED`, `PLAYER_ENTERING_WORLD`, `SPELLS_CHANGED`, `ACTIONBAR_SLOT_CHANGED`, `PLAYER_REGEN_ENABLED`, `SPELL_UPDATE_COOLDOWN`, `UNIT_SPELLCAST_SUCCEEDED`), slash commands.

## Forever combat limits (from the code's header notes)

In combat, aura reads throw and cooldown numbers are "secret values". The code:
- passes cooldowns to the Cooldown widget as duration objects instead of reading numbers;
- keeps the Paladin panel's last known state and updates it from the player's own casts;
- checks `issecretvalue` before using values;
- wraps risky calls in `Guard()`, which prints each distinct error once with the "Spell Cooldown Tracker error:" prefix.

Keep to these patterns when changing combat code.

## Commands

`/scdt` (or `options`, `config`) options window · `spells` / `track` Tracked spells window · `edit`, `lock`, `unlock` move frames · `swing` toggle combat-only swing timer · `size <16-96>` · `ignore <spell>` / `unignore <spell>` (current class/spec profile) · `reset` frame positions · `debug [spell]` diagnostics.

## Testing

There are no automated tests in this repo yet. At minimum:
```
luac5.1 -p SpellCDTracker.lua      # apt-get install -y lua5.1
bash tools/package.sh               # also checks every file the .toc lists exists
```
Then ask Anthony to test in-game; `/scdt debug` prints tracked-spell count, combat state, whether auras are locked and whether the secret-value API exists. Say plainly which parts were only syntax-checked.

## Releasing

1. Bump `## Version` in `SpellCDTracker.toc` (the only place the version appears).
2. `bash tools/package.sh` -> `dist/SpellCDTracker-v<Version>-forever.zip`, containing only `SpellCDTracker/` with the `.toc` and `SpellCDTracker.lua`. Or after merge: Actions > Package > Run workflow, which creates release `v<Version>`; it refuses a version that already has a release. The workflow has not yet been run on GitHub.
3. Anthony uploads to CurseForge (game version: Forever, release type: Release). Don't re-upload an existing version under a new file name; bump instead.

## Git workflow

- Never commit to `main`. Use a branch and open a PR; Anthony merges.
- `gh` is not installed in the cloud sessions. Open PRs with the GitHub API: `curl -X POST https://api.github.com/repos/Nekramess/SpellCDTracker/pulls -H "Content-Type: application/json" --data-binary @body.json` (the Content-Type header is required).
- Shallow clones only track `main`; after pushing a branch run `git config --replace-all remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*' && git fetch` so the branch shows as pushed.
- `*.zip` is gitignored.

## Related

Sister addon: Ready Macros (`Nekramess/ReadyMacros`), same packaging, workflow and conventions. Its `tools/tests/wowmock.lua` is a starting point if this repo gets tests.
