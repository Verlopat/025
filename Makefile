.PHONY: all run build test verify-sc verify-tso benchmark-e3 benchmark-e4 analyze figures reproduce clean
all: run
run: ; python3 Main.py
build: ; cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel 4
test: build
	ctest --test-dir build --output-on-failure
	python3 -m unittest discover -s tests -p 'test_*.py' -v
verify-sc:
	python3 -c "from verify.operational import explore; import json; print(json.dumps(explore(model='sc'),indent=2))"
verify-tso:
	python3 -c "from verify.operational import explore; import json; print(json.dumps(explore(model='tso'),indent=2))"
benchmark-e3: build
	python3 Main.py --experiments e3
benchmark-e4: build
	python3 Main.py --experiments e4
analyze:
	@test -n "$(RUN)" || { echo "Usage: make analyze RUN=output/testN"; exit 1; }
	python3 -m python.analysis $(RUN)
figures: analyze
reproduce: run
clean: ; rm -rf build
