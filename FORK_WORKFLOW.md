# Custom Hermes Agent Fork Workflow

This document describes the branch structure and workflow for maintaining a custom hermes-agent fork with independent feature branches that can be selectively combined.

## Overview

This fork uses a **modular feature branch strategy** where:

- `main` tracks upstream NousResearch/hermes-agent releases
- Each feature lives in its own independent branch based on `main`
- `dashed/my-hermes` is a merge commit that combines all desired features
- Jujutsu (jj) is used for version control alongside Git

This approach allows:
- Easy updates when upstream releases new versions
- Selective feature inclusion (enable/disable features by changing the merge)
- Clean separation of concerns
- Simple conflict resolution per-feature

**Important:** Every file must live on a feature branch. Files added only to the integration merge commit (`dashed/my-hermes`) will be **lost** when the integration is rebuilt.

## Remotes

| Remote | URL | Purpose |
|--------|-----|---------|
| `origin` | `git@github.com:dashed/hermes-agent.git` | Fork (push here) |
| `upstream` | `git@github.com:NousResearch/hermes-agent.git` | Upstream (pull from here) |

## Branch Structure

```
main (upstream)
│
├── docs/fork-workflow
│   └── This file (fork workflow documentation)
│
└── dashed/my-hermes (integration)
    └── Combines all active feature branches
```

> **Historical note:** Earlier feature branches (`fix/slack-mrkdwn-formatting`,
> `fix/container-systemctl-status`, `docs/slack-messages-tab-setup`) were
> dropped from the integration merge once upstream absorbed or superseded
> them. The branches remain on `origin` as historical reference. See
> [Dropping a Branch Absorbed or Superseded Upstream](#dropping-a-branch-absorbed-or-superseded-upstream)
> for the drop workflow.

### Branch Descriptions

| Branch | Purpose | Based on |
|--------|---------|----------|
| `main` | Tracks upstream hermes-agent | upstream/main |
| `docs/fork-workflow` | This file — fork workflow docs | main |
| `dashed/my-hermes` | Combined active features (currently just `docs/fork-workflow`) | active feature branches |

### Visual DAG

```
◆  main (upstream)
│
├── ○ docs/fork-workflow
│   │  - This document
│
└── ○ dashed/my-hermes (merge of active feature branches)
```

## Jujutsu (jj) Setup

This repo uses jj in colocated mode, meaning both `jj` and `git` commands work.

### Why jj?

- **Automatic rebasing**: When you update a parent, descendants auto-rebase
- **First-class conflicts**: Conflicts are stored in commits, resolve when convenient
- **Operation log**: Every operation can be undone with `jj undo`
- **Change IDs**: Stable identifiers that survive rebases (unlike git commit hashes)
- **Multi-parent commits**: Native support for merge commits with 3+ parents

## Updating from Upstream

When upstream releases a new version:

### Step 1: Fetch upstream changes

```bash
jj git fetch --remote upstream
```

### Step 2: Update main

```bash
jj bookmark set main -r upstream/main --allow-backwards
```

### Step 3: Rebase all feature branches onto new main

```bash
# This rebases ALL feature branch roots onto new main
# jj automatically rebases all descendants including dashed/my-hermes
jj rebase -s 'roots(::dashed/my-hermes ~ ::main)' -d main
```

### Step 4: Resolve any conflicts

```bash
# Check for conflicts
jj log -r 'conflicts()'

# For each conflicted commit:
jj new <conflicted-change-id>    # Work on top of conflict
# Edit files to resolve
jj squash                         # Move resolution into parent

# For non-interactive squash (skip editor prompt):
JJ_EDITOR=true jj squash --into <change-id>
```

**Important:** If you squash into a commit that has descendants (e.g., the integration merge), `jj squash` may absorb the merge commit. If this happens, recreate the integration merge and re-set the bookmark:

```bash
jj describe @ -m "integration: combine all feature branches"
jj bookmark set dashed/my-hermes -r @ --allow-backwards
```

### Step 5: Push updated branches

```bash
jj git push --tracked
```

## Adding a New Feature

### Step 1: Create feature branch from main

```bash
jj new main -m "feat: description of feature"
jj bookmark create my-new-feature
```

### Step 2: Develop the feature

```bash
# Make changes - they're auto-tracked
# When done with a logical unit:
jj new -m "next part of feature"

# Or edit the description:
jj describe -m "better description"
```

### Step 3: Add to integration branch

```bash
# Recreate dashed/my-hermes with the new feature included
# List ALL active feature branches as parents:
jj new docs/fork-workflow my-new-feature -m "integration: combine all feature branches"
jj bookmark set dashed/my-hermes -r @ --allow-backwards
```

### Step 4: Push

```bash
jj git push --tracked
```

## Removing a Feature

To remove a feature from the integration branch, recreate it without that feature's branch:

```bash
# Example: if features A, B, C were active and you wanted to remove B:
jj new A C -m "integration: combine all feature branches"
jj bookmark set dashed/my-hermes -r @ --allow-backwards
jj git push --tracked
```

## The Integration Branch (dashed/my-hermes)

`dashed/my-hermes` is a **merge commit with multiple parents**. It combines all feature branches into a single working build.

### How it works

```bash
# Create a merge with multiple parents:
jj new <branch1> <branch2> <branch3> -m "integration message"
```

When any parent branch is updated (e.g., after rebasing onto new upstream), the merge commit is automatically recreated by jj.

### What NOT to put on the integration branch

**Never add files directly to the integration merge commit.** The integration is rebuilt from scratch when feature branches are updated. Anything not on a feature branch will be lost. Always create a dedicated feature branch for new files (even documentation like this one).

## Dropping a Branch Absorbed or Superseded Upstream

When upstream merges our work or ships a superseding fix, the correct move is to **drop our branch from the integration merge** rather than rebase a stale duplicate.

### Detecting upstream absorption

During a rebase, check upstream for:

- **Squash-merges of our PRs.** When upstream squash-merges one of our PRs, the resulting commit is authored by the fork owner (e.g. `dashed`). Quick probe:
  ```bash
  git log --author=dashed upstream/main -20
  ```
  A matching commit whose message mirrors your PR title is a strong signal that upstream absorbed it.

- **Functionally-equivalent fixes.** Upstream may ship a superseding fix that touches the same files with a different (often more thorough) approach. Search by file:
  ```bash
  git log upstream/main -- path/to/file/we/touched.py
  ```

### Dropping workflow

1. **Verify the upstream change covers our branch's intent.** Diff our branch against upstream and confirm the behavior is equivalent or strictly better.
2. **Rebuild the integration merge WITHOUT the obsolete branch.** Example — dropping `fix/legacy` from an integration that contains `docs/fork-workflow`, `fix/legacy`, and `feat/new`:
   ```bash
   jj new docs/fork-workflow feat/new -m "integration: combine all feature branches"
   jj bookmark set dashed/my-hermes -r @ --allow-backwards
   ```
3. **Keep the dropped bookmark pointing at its last commit.** Do NOT delete local bookmarks or origin branches; they remain as historical reference until a dedicated cleanup pass.
4. **Close the related PR on the fork** with a comment referencing the upstream commit SHA (e.g. `CLOSED — upstream absorbed via NousResearch/hermes-agent@7f7b02b7`).
5. **Force-push the rebuilt integration and any rebased sibling branches:**
   ```bash
   jj git push --tracked
   ```

### When NOT to drop

- **Don't drop just because the rebase conflicts look scary.** Resolve conflicts first, then decide whether our version still adds value.
- **Don't drop if upstream behavior differs from ours.** If upstream's version is a subset of our fix, keep our branch and add a note explaining the delta. Alternatively, file a follow-up PR upstream to converge.

### Real example: 2026-04-12 rebase

Dropped two branches in one rebase:

| Branch | Upstream replacement |
|---|---|
| `fix/slack-mrkdwn-formatting` | [`7f7b02b7`](https://github.com/NousResearch/hermes-agent/commit/7f7b02b7) — upstream squash-merged our PR on 2026-04-09, authorship preserved |
| `fix/container-systemctl-status` | [`5e1197a4`](https://github.com/NousResearch/hermes-agent/commit/5e1197a4) — upstream shipped a more comprehensive fix via `hermes_constants.is_container()` + `_run_systemctl()` wrapper + `shutil.which` guard |

Both were closed with comments referencing the upstream commits, and the dropped branches remain on origin for historical reference.

## Re-parenting the Integration Merge After a Rebase

When a fresh upstream rebase moves `main` forward, the revset-based rebase in [Updating from Upstream](#step-3-rebase-all-feature-branches-onto-new-main) rewrites `docs/fork-workflow` onto the new tip — but it can leave the integration merge `dashed/my-hermes` with one parent still pointing at the **previous** `main`. The merge ends up with parents `{new docs/fork-workflow, OLD main}` instead of `{new docs/fork-workflow, new main}`. A leftover conflicted octopus-merge from an earlier rebase state sometimes also surfaces at the same time. Both are fixable without restarting the rebase.

### Detecting a stale merge parent

After `jj rebase -s 'roots(::dashed/my-hermes ~ ::main)' -d main` finishes, list the integration merge's parents:

```bash
jj log -r 'dashed/my-hermes-' --no-graph \
    -T 'commit_id ++ " " ++ bookmarks ++ "\n"'
```

A healthy result shows two lines whose SHAs match the current `main` tip and the current `docs/fork-workflow` tip. If one line matches the **pre-rebase** `main` SHA instead, the merge is stale. Also check for orphan conflicted merges from previous rebase states:

```bash
jj log -r 'conflicts()'
```

Any orphan octopus-merge that is no longer reachable from a bookmark belongs to the previous rebase and should be abandoned before re-parenting.

### Repair workflow

1. **Abandon any orphan conflicted integration merge.** If `jj log -r 'conflicts()'` surfaces a leftover merge from an earlier rebase state, remove it so it does not get picked up by the next operation:
   ```bash
   jj abandon <orphan-change-id>
   ```
2. **Re-parent the integration merge onto both current tips explicitly.** `jj rebase -r` rewrites a single commit without touching its descendants, and passing `-d` once per desired parent rebuilds the multi-parent merge:
   ```bash
   jj rebase -r dashed/my-hermes -d main -d docs/fork-workflow
   ```
   If additional feature branches are active, list them all after `-d`, one per flag, in the same order you would use with `jj new` when building a fresh integration.
3. **Verify both parents now point at the rebased SHAs.**
   ```bash
   jj log -r 'dashed/my-hermes-' --no-graph \
       -T 'commit_id ++ " " ++ bookmarks ++ "\n"'
   ```
   The output should list the current `main` and `docs/fork-workflow` tips — no stale SHAs.
4. **Push the rebuilt integration along with the other rebased branches:**
   ```bash
   jj git push --tracked
   ```

### Why `jj rebase -s` leaves the merge stale

The revset `roots(::dashed/my-hermes ~ ::main)` selects the roots of commits reachable from `dashed/my-hermes` but **not** reachable from `main`. Commits already in `main`'s history are deliberately excluded, which is what makes the rebase idempotent when `main` has not moved. The side effect: the feature branches under the integration merge get rebased (their roots are in the set), and the integration merge itself is rewritten because one of its parents — `docs/fork-workflow` — was rewritten; but the **other** parent of the merge is the previous `main`, which is never in the rebase set, so jj has nothing to translate it to. The resulting merge commit points its feature-branch parent at the new tip and its `main` parent at the pre-rebase commit. Re-running `jj rebase -r dashed/my-hermes -d main -d docs/fork-workflow` asserts both parents from scratch and produces the merge the rebase was meant to land on.

### Real example: 2026-04-22 rebase

Rebasing 1398 upstream commits from `0d0d27d4` to `c96a548b`:

| Stage | `dashed/my-hermes` parents | Orphan |
|---|---|---|
| After `jj rebase -s … -d main` | `{5fdedcd2 (new docs/fork-workflow), 0d0d27d4 (OLD main)}` | `d3708bba` (conflicted octopus) |
| After `jj abandon d3708bba` + `jj rebase -r dashed/my-hermes -d main -d docs/fork-workflow` | `{5fdedcd2 (new docs/fork-workflow), c96a548b (new main)}` | — |

The repair left the integration merge at `13de37957834` with both parents on the correct post-rebase SHAs, and `jj log -r 'conflicts()'` returned empty.

## Common jj Commands

### Navigation

```bash
jj log                              # View commit graph
jj log -r 'trunk()..@'              # Show commits between main and working copy
jj status                           # Current state
jj diff                             # Changes in working copy
```

### Branching

```bash
jj bookmark list                    # List bookmarks
jj bookmark create <name>           # Create at current commit
jj bookmark set <name> -r <rev>     # Move bookmark
jj bookmark set <name> --allow-backwards  # Move bookmark backward
```

### Editing history

```bash
jj edit <change-id>                 # Edit existing commit
jj new                              # Create new commit
jj squash                           # Move changes to parent
jj describe -m "message"            # Change commit message
jj abandon <change-id>              # Remove commit
```

### Rebasing

```bash
jj rebase -d main                   # Rebase current onto main
jj rebase -s <rev> -d <dest>        # Rebase rev and descendants
jj rebase -r <rev> -d <dest>        # Rebase only rev (not descendants)
```

### Syncing with Git

```bash
jj git fetch                        # Fetch from remote
jj git push --tracked               # Push tracked bookmarks
jj git push --bookmark <name>       # Push specific bookmark
```

### Undo mistakes

```bash
jj undo                             # Undo last operation
jj op log                           # View operation history
jj op restore <op-id>               # Restore to specific state
```

## Workflow Tips

### Always check status after operations

```bash
jj status && git status
```

### Non-interactive squash

When resolving conflicts by squashing into a specific commit, skip the editor prompt:

```bash
JJ_EDITOR=true jj squash --into <change-id>
```

### Watch for absorbed descendants after squash

When you `jj squash` into a commit that has descendants (like the integration merge), the squash may absorb the merge commit. After squashing, always verify:

```bash
jj log -r 'dashed/my-hermes'
```

### View what will be pushed

```bash
jj git push --dry-run --tracked
```

### Resolve conflicts in order

When rebasing creates conflicts in multiple commits:

1. Find all conflicts: `jj log -r 'conflicts()'`
2. Resolve parent commits first
3. Child commits may auto-resolve when parents are fixed

---

*Last updated: 2026-04-22*
