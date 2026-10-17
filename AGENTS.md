# Project Rules & Workflow Guidelines

## Git & Version Control Rules (MANDATORY)

1. **NEVER Push to `main` Directly:**
   - The `main` branch is protected. Under no circumstances should direct commits or pushes be made to `main`.
   - Always create and work on dedicated feature or fix branches branched from `main`.

2. **ALWAYS Ask Before Pushing Anything:**
   - Do NOT run `git push` autonomously.
   - Always ask the user for explicit review and approval before pushing any branch to the remote repository.

3. **Review Before Committing:**
   - Present changed files and diff summaries to the user for review before committing.

4. **Fire Review Agent Before Push:**
   - Always fire a dedicated code review agent (`code-reviewer`) to inspect git diffs, security, and correctness before asking for push approval.
   - Present the reviewer agent's findings and verdict in the summary to the user.

5. **Avoid Over-Engineering:**
   - Keep implementations clean, direct, simple, and pragmatic.
   - Do not over-engineer solutions with unnecessary abstractions, excess boilerplate, or speculative features unless explicitly requested.

6. **Write & Run Unit Tests Before Pushing:**
   - Always write targeted unit tests for any new tasks, endpoints, or features to verify correctness and prevent regressions.
   - Run the test suite before requesting review and push approval:
     - Backend: `PYTHONPATH=backend ./backend/.venv/bin/python -m unittest discover -s backend/tests`
     - Frontend: `npm run build` (in `frontend/`)
   - Ensure all tests pass cleanly without failures or errors.
   - Never push code with broken or failing tests.

