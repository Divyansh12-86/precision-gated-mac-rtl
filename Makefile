PYTHON ?= $(shell test -x .venv/bin/python3 && echo .venv/bin/python3 || echo python3)
VERILATOR = verilator
YOSYS = yosys

.PHONY: all data vectors sim quality activity synth noise mutation report nightly clean

all: data vectors sim quality activity synth noise report

data:
	$(PYTHON) scripts/fetch_data.py

vectors:
	$(PYTHON) sim/gen_vectors.py --all

sim:
	$(PYTHON) sim/run_regression.py

quality:
	$(PYTHON) sim/analyze.py --all

activity:
	$(PYTHON) sim/activity_report.py

synth:
	mkdir -p reports
	$(PYTHON) scripts/synth_runner.py

noise:
	$(PYTHON) sim/noise_sweep.py

mutation:
	$(PYTHON) scripts/mutation_check.py

report:
	$(PYTHON) scripts/generate_report.py

nightly:
	$(PYTHON) sim/run_regression.py --nightly

clean:
	rm -rf build* obj_dir/ *.vvp *.vcd /tmp/tb_*
