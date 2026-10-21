PYTHON = .venv/bin/python3
VERILATOR = verilator
YOSYS = yosys

.PHONY: all vectors sim quality activity synth report clean

all: vectors sim quality activity synth report

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
	$(YOSYS) -s scripts/synth_yosys.ys | tee reports/synth_yosys.rpt

report:
	$(PYTHON) scripts/generate_report.py

clean:
	rm -rf build/ obj_dir/ *.vvp *.vcd /tmp/tb_*
