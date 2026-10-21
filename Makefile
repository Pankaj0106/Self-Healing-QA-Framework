setup:
	python -m pip install -e ".[dev]"
	python -m playwright install chromium

test:
	pytest tests/ui -n 4

smoke:
	pytest tests/ui -m smoke -n 4

eval:
	pytest tests/eval -v

gate:
	python scripts/heal_gate.py --min 0.70

demo:
	python scripts/demo_heal.py

mcp-smoke:
	python scripts/mcp_smoke.py

mcp:
	python -m src.mcp_server.server

report:
	allure serve reports/allure-results
