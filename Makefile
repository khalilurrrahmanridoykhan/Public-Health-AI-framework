# One-command reproduction: `make reproduce` installs PHFrame, runs the test
# suite and certification gates, and regenerates every example output.

PYTHON ?= python
OUTPUT ?= outputs

.PHONY: reproduce install test certify contract dashboard clean

reproduce: install test certify contract dashboard

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

clean:
	rm -rf $(OUTPUT)
