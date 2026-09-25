.PHONY: lint lint-fix typecheck deptry vulture test run

lint:
	poetry run ruff check .

lint-fix:
	poetry run ruff check --fix .
	poetry run ruff format .

typecheck:
	poetry run pyright

deptry:
	poetry run deptry .

vulture:
	poetry run vulture .

test:
	poetry run pytest
