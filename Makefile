.PHONY: check check-changed test test-setup test-guidance test-packaging test-change \
	test-evidence test-memory test-web validate smoke compatibility-smoke \
	portable-compatibility-smoke telemetry-check core-reset-eval core-reset-release-eval

check: validate test

check-changed:
	@test -n "$(BASE)" || { echo "set BASE to the comparison ref, for example origin/main" >&2; exit 2; }
	PYTHONDONTWRITEBYTECODE=1 python3 scripts/impact_tests.py run --base "$(BASE)" \
		$(if $(filter 1 true yes,$(INCLUDE_UNTRACKED)),--include-untracked,)

validate:
	PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate_repo.py

test:
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v

test-setup:
	PYTHONDONTWRITEBYTECODE=1 python3 scripts/impact_tests.py run --group setup --lane python

test-guidance:
	PYTHONDONTWRITEBYTECODE=1 python3 scripts/impact_tests.py run --group guidance --lane python

test-packaging:
	PYTHONDONTWRITEBYTECODE=1 python3 scripts/impact_tests.py run --group packaging --lane python

test-change:
	PYTHONDONTWRITEBYTECODE=1 python3 scripts/impact_tests.py run --group change --lane python

test-evidence:
	PYTHONDONTWRITEBYTECODE=1 python3 scripts/impact_tests.py run --group evidence --lane python

test-memory:
	PYTHONDONTWRITEBYTECODE=1 python3 scripts/impact_tests.py run --group memory --lane python

test-web:
	PYTHONDONTWRITEBYTECODE=1 python3 scripts/impact_tests.py run --group web --lane python

smoke:
	PYTHONDONTWRITEBYTECODE=1 python3 tests/live_smoke.py

compatibility-smoke:
	PYTHONDONTWRITEBYTECODE=1 python3 tests/compatibility_smoke.py

portable-compatibility-smoke:
	PYTHONDONTWRITEBYTECODE=1 python3 tests/portable_compatibility_smoke.py

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
