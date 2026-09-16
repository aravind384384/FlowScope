# Checking Git Repository Status

## Overview

This guide demonstrates how to check the active Git branch and inspect the current status of the working directory, including modified and untracked files.

## Prerequisites

- A working directory initialized as a Git repository.

## Step 1: Verify the Active Branch [VERIFICATION]

List local branches and identify which branch is currently checked out.

```bash
git branch
```

```text
* main
```

## Step 2: Inspect Working Directory Status [VERIFICATION]

Check the state of the working tree to view untracked files, modified files, and staged changes.

```bash
git status
```

```text
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
	modified:   flowscope.py

Untracked files:
	flowscope_debug.py
	sessions/
```

## Result

You have successfully verified that you are on the `main` branch and identified all modified and untracked files within the repository.