# Extracting this project into its own repository

This project was developed inside the [coronial](https://github.com/changyang1230/coronial)
repository for convenience, but it is unrelated to it — a media-content study has no
business living in a coroners findings database. These are the steps to give it its own
repository, keeping the commit history.

Once done, delete this file.

## What makes this clean

- **Nothing was ever merged into coronial's `main`.** The work lives entirely on the
  branch `claude/tesla-media-bias-study-304eg5`. Coronial's history is untouched, so
  there is nothing to revert — the cleanup is one branch deletion.
- `git subtree split` rewrites the three commits so this directory's contents sit at the
  repository root, and drops everything outside it (including the `.gitignore` edit made
  to coronial's root — this project carries its own).

## 1. Get the branch up to date

```bash
cd /path/to/coronial
git fetch origin
git checkout claude/tesla-media-bias-study-304eg5
git pull
```

## 2. Split the history

```bash
git subtree split --prefix=research/tesla-headline-salience -b tesla-study
```

Verify before going further — the contents should be at the root and the history intact:

```bash
git ls-tree --name-only tesla-study     # PROTOCOL.md, src, tests, ... (no research/)
git log --oneline tesla-study           # 3 commits
```

## 3. Create the new repository

On GitHub: **New repository** → name it (e.g. `tesla-headline-study`) → **do not**
initialise with a README, `.gitignore`, or licence. An empty repository avoids an
unrelated-histories merge on the first push.

## 4. Push

No clone needed — push the split branch straight from the coronial working copy:

```bash
git remote add tesla-study https://github.com/<you>/tesla-headline-study.git
git push tesla-study tesla-study:main
```

## 5. Open the new repository as its own VS Code workspace

```bash
cd ~/projects            # wherever you keep repos
git clone https://github.com/<you>/tesla-headline-study.git
code tesla-headline-study
```

Then rebuild the environment at the new root:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests -q     # expect 63 passed
```

## 6. Clean up

```bash
cd /path/to/coronial
git checkout main
git remote remove tesla-study
git branch -D tesla-study claude/tesla-media-bias-study-304eg5
git push origin --delete claude/tesla-media-bias-study-304eg5
```

Coronial is now exactly as it was. Do **not** merge the study branch into `main` first —
merging and then deleting would leave the study permanently in coronial's history for no
reason.

## 7. Worth doing in the new repository

- **Add a licence.** Protocol §14 commits to publishing the code and the incident-level
  dataset openly. MIT or Apache-2.0 for the code; CC-BY-4.0 suits the dataset if you
  publish it separately.
- **Check the repository is public** if you intend the freeze tag to serve as the public
  timestamp that a pre-registration DOI would have provided (Protocol §0).
- **Tag the freeze** when you reach Phase 2: `git tag protocol-v1 && git push --tags`.
- **Delete this file** — it has done its job.
