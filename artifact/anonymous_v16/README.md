# Anonymous v16 experiment artifact

This package contains experiment code and machine-readable evidence only. It
does not contain a manuscript, author metadata, repository history, credentials,
private keys, or private host configuration.

Requirements:

- Python 3.11 or newer;
- Node.js 22 and npm;
- Windows, Linux, or macOS with localhost TCP available.

From the extracted bundle root, run:

```bash
python reproduce.py
```

Use `--skip-install` only after the lockfile-pinned Node dependencies have
already been installed in `artifact/joint_incidence_refinement/node_modules`.

The command verifies the finite model and stress fixture, regenerates the
35-route controlled OPE capture, verifies all authenticated requests, runs the
certificate generator in byte-comparison mode, invokes the independent
standard-library verifier, and checks the committed size/scaling experiment.
The final line is:

```text
ANONYMOUS_V16_AUTHENTICATED_RELATIVE_PROCESS_CERTIFICATE=PASS
```

The positive value is four accounting units and applies only to the admitted
local execution model. It is not a deployment-global or production-economic
claim.
