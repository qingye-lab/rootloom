class RetryBudget:
    def __init__(self, max_attempts: int) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.max_attempts = max_attempts
        self.attempts_used = 0

    def consume(self) -> bool:
        if self.attempts_used >= self.max_attempts:
            return False
        self.attempts_used += 1
        return True
