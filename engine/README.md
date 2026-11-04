# biorun: the pipeline engine

A small Rust CLI that runs a research pipeline step by step and records exactly what ran. No dependencies outside
the Rust standard library, so it builds offline on any machine with Rust 1.75 or newer.

```sh
cargo build --release --manifest-path engine/Cargo.toml     # binary: engine/target/release/biorun
biorun run <pipeline.toml> [--workdir DIR] [--from STEP | --only STEP]
biorun verify <workdir>/biorun/<run>
biorun hash <file>...
```

## Pipeline files

A strict subset of TOML: strings, arrays of strings and `[[step]]` tables. Unknown keys are errors.

```toml
name = "crambin-1ns"
description = "optional"

[[step]]
name = "simulate"
command = ["python", "{pipeline_dir}/simulate.py"]   # argv, run without a shell, in the work directory
inputs = ["1crn.pdb"]                                 # must exist before the step runs; hashed
outputs = ["trajectory.dcd"]                          # must exist after it succeeds; hashed
stdout = "simulation.log"                             # optional; default is a log in the run directory
expect = ["<sha256>  1crn.pdb"]                       # optional pins, checked after the step
```

`{pipeline_dir}` expands to the directory holding the pipeline file, so scripts are found wherever the repository
is checked out while data and outputs stay in the work directory.

## Run records

Each run gets `<workdir>/biorun/<UTC stamp>-<pipeline>/` with:

| File | Holds |
| --- | --- |
| `run.json` | Engine version, pipeline file and its SHA-256, git commit and dirty flag, host, start and finish times, status; per step the argv, exit code, duration and input and output hashes. Rewritten after every step, so an interrupted run still shows how far it got. |
| `hashes.sha256` | Every input and output in `sha256sum` format, relative to the work directory. `cd <workdir> && sha256sum -c biorun/<run>/hashes.sha256` checks a run without biorun. |
| `pipeline.toml` | The exact pipeline file that ran. |
| `<step>.stderr.log`, `<step>.stdout.log` | Step output. |

A step that fails, can't start, is missing an input, doesn't produce a declared output or doesn't match a pin
stops the run with exit status 1; usage and file errors exit with 2.

## Not yet

Caching or skipping unchanged steps, parallel steps, GPU telemetry, and resource limits. `--from` resumes a
failed run by hand.
