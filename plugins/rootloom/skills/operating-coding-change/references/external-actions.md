# External actions

Load this Reference before deployment, release, infrastructure, production data, or
other external execution.

1. Verify the authorized operation type, target, branch/environment/account, scope, and
   blast radius from the current task and live evidence.
2. Use a plan, preview, dry-run, backup, canary, staged rollout, or reversible mode
   where available.
3. Verify credentials and permissions without printing or copying secrets.
4. Define the signal that stops rollout and the exact rollback or compensation action.
5. If current authority does not cover the next action, finish independent preparation
   already authorized, then request **Single action** for the concrete displayed action.
   Explain **Standard** or **Full** when the user asks to change modes. Standard remains
   cross-task authority for non-high-risk steps of explicit goals; Full remains limited
   to the current task's operation type and scope. Never infer Full or repeat an approval
   already granted. Preserve explicit independent approvals and stage acceptance.
6. Re-read the target before a destructive operation and verify resulting external
   state afterward. A submitted command is not proof of success.

Platform, organization, sandbox, credential, and hard-deny controls remain authoritative.
