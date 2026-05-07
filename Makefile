PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: test repro-2014 repro-2024 figures arxiv-figures arxiv-paper

test:
	$(PYTHON) -m pytest -q

repro-2014:
	$(PYTHON) -m cascade.simulate
	$(PYTHON) -m cascade.replay --year 2014

repro-2024:
	$(PYTHON) -m cascade.simulate
	$(PYTHON) -m cascade.replay --year 2024

figures:
	$(PYTHON) scripts/export_release_artifacts.py

arxiv-figures:
	MPLBACKEND=Agg $(PYTHON) papers/02_arxiv/scripts/render_replay_modes_figure.py

arxiv-paper: arxiv-figures
	papers/02_arxiv/scripts/build_arxiv.sh
