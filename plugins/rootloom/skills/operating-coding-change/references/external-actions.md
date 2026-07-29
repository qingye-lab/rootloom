# External actions

Load this Reference before deployment, release, infrastructure, production data, or
other external execution.

1. Verify the authorized operation type, target, branch/environment/account, scope, and
   blast radius from the current task and live evidence.
2. Use a plan, preview, dry-run, backup, canary, staged rollout, or reversible mode
   where available.
3. Verify credentials and permissions without printing or copying secrets.
4. Define the signal that stops rollout and the exact rollback or compensation action.
5. If the current authority does not cover the next action, offer exactly:
   **Single action** for the displayed action once; **Standard** for non-high-risk
   actions across explicit tasks; **Full** for routine and high-risk actions only in
   this task's stated operation type and scope. Never infer Full.
6. Re-read the target before a destructive operation and verify resulting external
   state afterward. A submitted command is not proof of success.

Platform, organization, sandbox, credential, and hard-deny controls remain authoritative.
