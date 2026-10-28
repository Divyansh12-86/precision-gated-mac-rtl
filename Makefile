PYTHON ?= $(shell test -x .venv/bin/python3 && echo .venv/bin/python3 || echo python3)
VERILATOR = verilator
YOSYS = yosys

.PHONY: all data vectors full-vectors sim quality activity synth noise mutation report nightly clean bundle demo-rom viewer-test

all: data vectors sim quality activity synth noise report

data:
	$(PYTHON) scripts/fetch_data.py

vectors:
	$(PYTHON) sim/gen_vectors.py --all

full-vectors:
	$(PYTHON) sim/gen_vectors.py --full

demo-rom:
	$(PYTHON) scripts/gen_demo_noisy.py

viewer-test:
	$(PYTHON) scripts/ecg_live_viewer.py --selftest

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
	$(PYTHON) scripts/generate_pdf.py

nightly: full-vectors
	$(PYTHON) sim/run_regression.py --nightly

bundle:
	$(PYTHON) scripts/make_verification_bundle.py --run-checks

clean:
	rm -rf build* obj_dir/ *.vvp *.vcd /tmp/tb_*
