# Checking Git Repository Status and Active Branch

## Overview

This guide explains how to check the active branch and review the current status of tracked and untracked files within a Git repository.

## Prerequisites

- Git installed and available in the system PATH.
- A local Git repository initialized in the current working directory.

## Step 1: Check Active Branch [VERIFICATION]

List local branches to identify which branch is currently checked out.

```bash
git branch
```

Expected output:
```text
* main
```

## Step 2: Inspect Repository Status [VERIFICATION]

Check the state of the working directory and staging area to view modified files, untracked changes, and commit status relative to the remote branch.

```bash
git status
```

Expected output:
```text
On branch main
Your branch is ahead of 'origin/main' by 1 commit.

Changes not staged for commit:
	modified:   flowscope.py
	modified:   flowscope_curator.py
	modified:   flowscope_parser.py

Untracked files:
	sessions/2026-09-16/Parser-Test-10/
	...
```

## Result

The current active branch was verified as `main`, and the working tree status was inspected, revealing modified source files and uncommitted session directories.