# Checking Git Repository Status in FlowScope

## Overview

This guide demonstrates how to check the status of a Git repository to review modified source files and untracked session logs in the FlowScope project directory.

## Prerequisites

- Git installed and accessible via command line
- An active Git repository (e.g., FlowScope project directory)

## Step 1: Inspect Working Directory and Branch Status [VERIFICATION]

Run `git status` to view the current branch state, local commits pending push, unstaged changes to tracked files, and newly created untracked session directories.

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
	modified:   flowscope_parser.py

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	sessions/2026-09-16/Parser-Test-6/
	sessions/2026-09-16/Parser-Test-8/
	sessions/2026-09-16/Parser-Test-9/
```

## Result

The repository status was successfully inspected, identifying two modified source files (`flowscope.py` and `flowscope_parser.py`) and three untracked session folders ready to be staged or managed.