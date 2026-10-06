# Releasing SpellCDTracker

## File name standard (all our addons)

Every release zip is named **`<Addon>-v<Version>-forever.zip`**, nothing else:

| Part | Value for this addon | Where it comes from |
|---|---|---|
| `<Addon>` | `SpellCDTracker` (no spaces, same as the folder and the `.toc` name) | `package-as` in `.pkgmeta`, else the `.toc` file name |
| `v<Version>` | `v0.12.1` | the `## Version:` line in `SpellCDTracker.toc` |
| `-forever` | always | marks the Forever build, like other Forever addons on CurseForge |

Example: `SpellCDTracker-v0.12.1-forever.zip`

Rules:
- **Build the zip with `tools/package.sh`** (or the "Package" GitHub Action, which calls it). Never zip by hand and never rename the file. Both the script and the action already use this pattern.
- **Upload the file exactly as built.** CurseForge shows the file name as the display name, so do not retype it in the upload form. Wrong examples that were uploaded before: `v0.12.0 SpellCDTracker.zip` and `v0.10.2 SpellCDTracker.zip` (version first, with a space).
- **The display name in the game and on the project page can differ** (it is the `## Title:` in the `.toc`). The zip name, folder, `.toc` file name, saved variables and slash command keep the internal name so installs and settings carry over.
- **One version, one file.** Bump `## Version:` for every release. Never upload a different build under a version number that already exists, and never re-upload a version under a new file name.
- If a wrongly named file is already on CurseForge, upload the next version with the correct name and archive the wrong one. Do not delete it.
- The internal name does not change when the display name does.

## Release steps
1. Branch, make the change, bump `## Version:` in `SpellCDTracker.toc`.
2. Run `bash tools/package.sh`; check the printed name matches the standard above.
3. Open a PR; Anthony merges. Never commit to `main`.
4. Upload the zip from `dist/` as built (Release type unless Anthony says otherwise). Game version: 1.60.1 (Forever).
5. Paste the change summary for the new version only.
