# One-command reproduction: `make reproduce` installs PHFrame, runs the test
# suite and certification gates, and regenerates every example output.

PYTHON ?= python
OUTPUT ?= outputs

.PHONY: reproduce install test certify contract openapi config-schema dashboard reference clean

reproduce: install test certify contract openapi config-schema dashboard reference

install:
	$(PYTHON) -m pip install -e '.[dev]'

test:
	$(PYTHON) -m pytest -q

certify:
	$(PYTHON) -m pip install bandit pip-audit
	$(PYTHON) -m pip_audit . --progress-spinner off
	bandit -q -r src/public_health_framework -ll

contract:
	$(PYTHON) -m public_health_framework.contract > docs/public-api-contract.json

openapi:
	$(PYTHON) -m public_health_framework.http_reference --write docs

config-schema:
	$(PYTHON) -m public_health_framework.config_schema --write docs

dashboard:
	mkdir -p $(OUTPUT)
	$(PYTHON) -m public_health_framework analyze examples/malaria_surveillance.csv \
		--location district --date report_date --value cases --population population \
		--category facility_type --title "Malaria Surveillance Dashboard" \
		--output $(OUTPUT)/malaria-dashboard.html
	$(PYTHON) -m public_health_framework analyze examples/case_reports.csv \
		--location district --date report_date --value cases --population population \
		--category disease --title "Case Reports Dashboard" \
		--output $(OUTPUT)/case-reports-dashboard.html

reference:
	cd examples/malaria-surveillance && $(PYTHON) -m public_health_framework check
	cd examples/malaria-surveillance && $(PYTHON) -m public_health_framework import facility_reports ../malaria_surveillance.csv

clean:
	rm -rf $(OUTPUT)
