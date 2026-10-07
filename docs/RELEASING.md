# Releasing SpellCDTracker

## File name standard (all our addons)

Every release zip is named **`<Addon>-v<Version>-forever.zip`**, nothing else:

| Part | Value for this addon | Where it comes from |
|---|---|---|
| `<Addon>` | `SpellCDTracker` (no spaces, same as the folder and the `.toc` name) | `package-as` in `.pkgmeta`, else the `.toc` file name |
| `v<Version>` | `v0.13.0` | the `## Version:` line in `SpellCDTracker.toc` |
| `-forever` | always | marks the Forever build, like other Forever addons on CurseForge |

Example: `SpellCDTracker-v0.13.0-forever.zip`

Rules:
- **Build the zip with `tools/package.sh`** (or the "Package" GitHub Action, which calls it). Never zip by hand and never rename the file. Both the script and the action already use this pattern.
- **Upload the file exactly as built.** CurseForge shows the file name as the display name, so do not retype it in the upload form. Wrong examples that were uploaded before: `v0.12.0 SpellCDTracker.zip` and `v0.10.2 SpellCDTracker.zip` (version first, with a space).
- **The display name in the game and on the project page can differ** (it is the `## Title:` in the `.toc`). The zip name, folder, `.toc` file name, saved variables and slash command keep the internal name so installs and settings carry over.
- **One version, one file.** Bump `## Version:` for every release. Never upload a different build under a version number that already exists, and never re-upload a version under a new file name.
- If a wrongly named file is already on CurseForge, upload the next version with the correct name and archive the wrong one. Do not delete it.
- The internal name does not change when the display name does.

## Where the zip lives (download it here, upload it to CurseForge)
The current release zip is kept in this repo: **`releases/SpellCDTracker-v<Version>-forever.zip`**. The folder holds exactly one zip; older ones are removed from it and stay in git history.
- Download: open the file on GitHub and use Download, or use `https://github.com/Nekramess/SpellCDTracker/raw/main/releases/<zip name>` once it is on `main`. Upload that file to CurseForge as is.
- Refresh it with `bash tools/release.sh`. It calls `tools/package.sh`, so the name rule above still holds. Commit the refreshed zip together with the change it contains.
- The `Tests` Action runs `tools/check-release.sh` and fails when `releases/` is empty, holds more than one zip, has a name that does not match the `.toc` version, or holds files that differ from a fresh build. A stale zip cannot be merged.
- `releases/` is in `.pkgmeta`'s ignore list, so it is never packed into the addon zip.

## Working on a change (one PR, one version)
- One piece of work = one branch = one PR. While Anthony tests and changes go back and forth, every tweak is another commit on the same branch and PR, and `## Version:` stays the same (no bump per tweak).
- Run `bash tools/release.sh` in every commit that changes addon files, so the zip in the repo is always the one Anthony downloads to test. Test zips carry the working version; only the zip that is on `main` is a release.
- The version is finalized only when Anthony says "push": pick the number, bump `## Version:`, run `bash tools/release.sh`, update the docs and CurseForge notes, and push to the same PR.

## Release steps
1. Branch from `main` (never commit to `main`) and make the change.
2. When Anthony says "push": set the final `## Version:` in `SpellCDTracker.toc`, run `bash tools/release.sh`, check the printed name matches the standard above, and run the tests.
3. Open or update the PR; Anthony merges.
4. Download `releases/<zip>` from `main` and upload it to CurseForge as is (Release type unless Anthony says otherwise). Game version: 1.60.1 (Forever).
5. Paste the change summary for the new version only.
