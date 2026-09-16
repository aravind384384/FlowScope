# Inspect Git Repository Status

## Overview

This guide explains how to check the active branch and inspect the current status of a local Git repository to identify unpushed commits, modified files, and untracked directories.

## Step 1: Check Current Git Branch [VERIFICATION]

Display local branches to verify which branch is currently active.

```bash
git branch
```

```text
* main
```

## Step 2: Check Working Directory Status [VERIFICATION]

View the status of the repository to check for uncommitted changes, untracked files, and local branch sync status with remote.

```bash
git status
```

```text
On branch main
Your branch is ahead of 'origin/main' by 1 commit.
  (use "git push" to publish your local commits)

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   flowscope.py

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	sessions/2026-09-16/Parser-Test-6/
	sessions/2026-09-16/Parser-Test-8/
```

## Result

The repository status was successfully verified on branch `main`. The working tree contains one modified file (`flowscope.py`), two untracked test directories, and one unpushed local commit.