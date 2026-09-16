# Checking Git Repository Status and Active Branch

## Overview

This guide explains how to inspect the working tree status and verify the active branch within a Git repository.

## Step 1: Check Working Tree Status [VERIFICATION]

Display the state of the working directory and staging area to identify modified, staged, or untracked files.

```bash
git status
```

```text
On branch main
Changes not staged for commit:
    modified:   flowscope.py

Untracked files:
    flowscope_debug.py
    sessions/
```

## Step 2: Verify Active Branch [VERIFICATION]

List local branches and highlight the currently active branch.

```bash
git branch
```

```text
* main
```

## Result

The current repository status was inspected, showing modified and untracked files while confirming the active working branch is `main`.