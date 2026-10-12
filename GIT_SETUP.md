# Create commits and publish this implementation to repository 025

From the extracted project directory (`025/`) on Ubuntu:

```bash
python3 --version
g++ --version
cmake --version
ninja --version
git --version
python3 Main.py
```

## Initialize and commit in logical batches

```bash
cd 025  # skip this if you are already inside the directory
git init
git branch -M main

git add CMakeLists.txt CMakePresets.json include/ src/ tests/unit.cpp
git commit -m "Implement deterministic CAS-based concurrent DSU and native tests"

git add Main.py python/ verify/ tests/test_*.py configs/ requirements.txt requirements-optional.txt pyproject.toml Makefile
git commit -m "Add model exploration, experiment pipeline and analysis"

git add README.md GIT_SETUP.md docs/ LICENSE CITATION.cff .env.example .gitignore .github/ scripts/ workloads/fixed/ output/.gitkeep
git commit -m "Document experiment scope and add reproducibility tooling"

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin https://github.com/Verlopat/025.git
else
  git remote add origin https://github.com/Verlopat/025.git
fi

git push -u origin main
```

GitHub may ask you to authenticate with a browser or personal access token. GitHub password authentication for HTTPS Git pushes is not supported. You can use the GitHub CLI (`gh auth login`) if installed. The repository already exists, so there is no need to create another one. Run outputs under `output/testN` and build binaries are ignored by `.gitignore`.
