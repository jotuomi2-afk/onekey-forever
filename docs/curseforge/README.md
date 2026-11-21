# CurseForge

- `icon.png` — the project icon (400×400, original art).
- `description.md` — the project description (paste into the CurseForge form).
- Summary line: *One key for leveling in WoW: Forever – druid and every class. Every action is your own key press.*

Uploads: `.github/workflows/curseforge.yml` sends the zip of each published
GitHub release once the owner has set the secret `CF_API_KEY` and the
variables `CF_PROJECT_ID` and `CF_GAME_VERSION` (Settings → Secrets and
variables → Actions). A run without `CF_GAME_VERSION` prints the version
names CurseForge knows. It can also be run by hand (Actions → curseforge →
Run workflow, with the tag).
