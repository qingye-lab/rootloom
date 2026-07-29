from loom_eval.budget import RetryBudget


def retry_status(budget: RetryBudget) -> dict[str, int]:
    return {"attempts_used": budget.attempts_used}
