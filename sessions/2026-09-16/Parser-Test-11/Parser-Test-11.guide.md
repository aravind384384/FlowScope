# Checking Git Repository Status

## Overview

This guide explains how to inspect the current Git branch and check the status of modified and untracked files in a repository.

## Prerequisites

- A Git repository initialized or cloned on your local machine.

## Step 1: Verify Active Branch [VERIFICATION]

Check which Git branch is currently active in the repository working directory.

```bash
git branch
```

```text
* main
```

## Step 2: Inspect Working Directory Status [VERIFICATION]

Display uncommitted changes, staged files, and untracked files to review the state of the repository.

```bash
git status
```

```text
On branch main
Your branch is ahead of 'origin/main' by 1 commit.

Changes not staged for commit:
	modified:   flowscope.py
	modified:   flowscope_parser.py
```

## Result

The active branch and repository state—including local commits, modified files, and untracked directories—have been successfully verified.