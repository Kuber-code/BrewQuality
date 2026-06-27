# Convenience targets. On Windows run the equivalent python -m commands directly,
# or use `make` via Git Bash / WSL.

.PHONY: install data run report test audit clean

install:
	pip install -r requirements.txt

data:
	python -m brewquality.generate_data --orders 5000 --seed 42

run:
	python -m brewquality.pipeline --reset

report:
	python -m brewquality.dq_report

test:
	pytest

audit:
	python -m brewquality.ci_audit

clean:
	python -c "import shutil, pathlib; shutil.rmtree(pathlib.Path('data/lake'), ignore_errors=True)"
