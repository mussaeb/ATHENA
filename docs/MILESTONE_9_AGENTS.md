# Milestone 9: Approved Plans

ATHENA can break a task into steps and run them one approval at a time.

## Commands

```text
/tools
/plan summarize README.md and show the git status
/approve
/reject
```

`/plan` asks the model for steps. A step runs only when its verb is on the allowlist:

- `search_docs`
- `web_search`
- `recall_history`
- `read_file`
- `list_files`
- `git_status`
- `git_diff`
- `git_log`
- `infra_status`
- `run_tests`

`/approve` runs the next pending step and records it in `logs/safety/safety.jsonl`. `/reject` skips that step. File writes stay on `/propose` and `/apply yes`, so a plan cannot edit the tree by itself.

If the model suggests a shell command or any other verb, that line is marked rejected and is not run.

## Example

```text
/plan find what the README says about memory and list recent commits
/approve
/approve
```

The first approval might read `README.md`. The second might show `git log`. You can read each result before the next approval.

Scheduled checks are still later. This milestone is the approval gate and the safety log.
