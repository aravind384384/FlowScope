# Checking Git Repository Status and Active Branch

## Overview

This guide demonstrates how to inspect the working tree status and verify the active branch within a Git repository.

## Prerequisites

- Git CLI installed and configured.
- An initialized local Git repository.

## Step 1: Inspect Repository Working Tree Status [VERIFICATION]

Check the current status of the repository to view modified files, untracked changes, and commit alignment with the remote branch.

```bash
git status
```

**Expected Result:**
Displays modified files (such as `flowscope.py`) and indicates whether the local branch is ahead of `origin/main`.

## Step 2: Verify the Active Branch [VERIFICATION]

List local branches to confirm which branch is currently checked out.

```bash
git branch
```

**Expected Result:**
```text
* main
```

## Result

The current working tree status and active Git branch were successfully identified and verified.