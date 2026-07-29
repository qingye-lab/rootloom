.PHONY: test check-polluting

test:
	python3 -m unittest discover -s tests -v

check-polluting:
	python3 -m unittest discover -s tests -v
	@echo "verification touched the worktree" > verification-output.txt
