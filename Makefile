.PHONY: check test validate smoke compatibility-smoke telemetry-check \
	core-reset-eval core-reset-release-eval

check: validate test

validate:
	PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate_repo.py

test:
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v

smoke:
	PYTHONDONTWRITEBYTECODE=1 python3 tests/live_smoke.py

compatibility-smoke:
	PYTHONDONTWRITEBYTECODE=1 python3 tests/compatibility_smoke.py

telemetry-check:
	PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_vibeloft_runtime.py

core-reset-eval:
	PYTHONDONTWRITEBYTECODE=1 python3 evals/core-reset/evaluate.py

core-reset-release-eval:
	@test -n "$(CORE_RESET_RESULTS)" || { echo "set CORE_RESET_RESULTS to a v2 scored result" >&2; exit 2; }
	PYTHONDONTWRITEBYTECODE=1 python3 evals/core-reset/evaluate.py \
		--results "$(CORE_RESET_RESULTS)" \
		--require-behavioral \
		--minimum-repetitions 3
