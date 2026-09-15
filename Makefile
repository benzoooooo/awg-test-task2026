.PHONY: install lint format typecheck test contracts ui-install ui-lint ui-typecheck ui-test ui-build ui-package package package-verify ci-check timelog-start timelog-dod privacy-check

POETRY ?= poetry
PNPM ?= pnpm
NODE20_BIN ?= $(shell [ -x /usr/local/opt/node@20/bin/node ] && echo /usr/local/opt/node@20/bin || echo)
export PATH := $(if $(NODE20_BIN),$(NODE20_BIN):)$(HOME)/.local/bin:$(PATH)

install:
	$(POETRY) install
	$(MAKE) ui-install

ui-install:
	cd ui && $(PNPM) install

lint:
	$(POETRY) run ruff check src tests fixtures scripts
	$(POETRY) run ruff format --check src tests fixtures scripts
	$(MAKE) ui-lint

format:
	$(POETRY) run ruff check --fix src tests fixtures scripts
	$(POETRY) run ruff format src tests fixtures scripts

typecheck:
	$(POETRY) run mypy
	$(MAKE) ui-typecheck

test:
	$(POETRY) run pytest
	$(POETRY) run lint-imports
	$(MAKE) ui-test

contracts:
	$(POETRY) run python scripts/export_contracts.py

ui-lint:
	cd ui && $(PNPM) run lint

ui-typecheck:
	cd ui && $(PNPM) run typecheck

ui-test:
	cd ui && $(PNPM) run test

ui-build:
	cd ui && $(PNPM) run build

ui-package: ui-build
	bash scripts/package_ui.sh

package: ui-package
	bash scripts/package_dist.sh

package-verify: package
	$(POETRY) run python scripts/package_verify.py --dist dist

ci-check: lint typecheck test contracts privacy-check
	git diff --check

privacy-check:
	bash scripts/privacy_check.sh

timelog-start:
	@ts=$$(date -u +'%Y-%m-%dT%H:%M:%SZ'); \
	printf '| build_started | %s |\n' "$$ts" >> TIMELOG.md; \
	echo "recorded build_started at $$ts"

timelog-dod:
	@ts=$$(date -u +'%Y-%m-%dT%H:%M:%SZ'); \
	printf '| dod_submitted | %s |\n' "$$ts" >> TIMELOG.md; \
	echo "recorded dod_submitted at $$ts"
