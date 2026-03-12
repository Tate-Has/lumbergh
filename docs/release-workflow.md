# Release Workflow

When the user says "release" (or "release minor", "release major"):

## Steps

1. **Lint**: Run `./lint.sh` — abort if it fails
2. **Clean tree**: Run `git status` — if uncommitted changes, ask user whether to commit them first
3. **Determine bump level**: Review commits since last tag:
   ```
   git log $(git describe --tags --abbrev=0)..HEAD --oneline
   ```
   - **patch** (default): bug fixes, small tweaks, UI polish
   - **minor**: new features, new endpoints, meaningful UX additions
   - **major**: breaking changes, large rewrites
   - User can override by saying "release minor" or "release major"
4. **Confirm**: Tell the user what version will be released (e.g. "v0.1.4 -> v0.1.5") and the bump reasoning before running the script
5. **Release**: Run `./release.sh <level> -y`
6. **Monitor all workflows**: A tag push triggers multiple workflows. Watch them all:
   ```
   gh run list --commit <tag> --limit 10 --json status,conclusion,url,name,workflowName
   ```
   The relevant workflows are:
   - **Release Stable** (triggered by tag push) — builds, creates GitHub release, publishes to PyPI
   - **CI** (triggered by any push to main) — lint + test + build
   - **Release Alpha** (triggered after CI succeeds on main) — builds alpha, publishes to PyPI
   - **Pages** (triggered if docs/ changed on main) — deploys docs

   Poll every 30 seconds until all triggered runs reach a terminal state (completed/failure/cancelled). Report each workflow's result and URL.
