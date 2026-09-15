# Vendored host example

Demonstrates the package-release flow: build a wheel in the library repo, copy it
into `vendor/`, and install it from `requirements.txt`.

```bash
# from repository root after `make package`
cp dist/awg_gitpulse_test-*.whl examples/host-vendor/vendor/
cd examples/host-vendor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
GITPULSE_REPO_PATH=/path/to/any/git/repo uvicorn app:app --port 8001
```

Open `http://127.0.0.1:8001/git/`.
