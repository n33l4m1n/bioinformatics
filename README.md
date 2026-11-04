# Bioinformatics

Research pipelines in five verticals, run and recorded by one engine. Every run writes down what ran, on which
inputs, at which code revision, with checksums for everything it read and wrote.

| Vertical | Status | What it does |
| --- | --- | --- |
| [sequence](sequence/README.md) | Working | Validated DNA FASTA parsing and composition (GC) reports in text, JSON or TSV, with a provenance manifest for the bundled data |
| [structure](structure/README.md) | Working | GPU molecular dynamics (OpenMM) and trajectory analysis (MDAnalysis); first run: crambin, 1 ns |
| [expression](expression/README.md) | Planned | Reprogramming and aging: reproducible analysis of measured cell states |
| [dna-models](dna-models/README.md) | Planned | Evaluation of small DNA models that fit one consumer GPU |
| [functional-genomics](functional-genomics/README.md) | Planned | AI-native functional genomics: model predictions of sequence function, tested against measured data |

The [engine](engine/README.md), `biorun`, is a dependency-free Rust CLI. A pipeline is a short TOML file of steps;
`biorun run` executes them in order and leaves a run record that `biorun verify`, or plain `sha256sum -c`, can
check later.

## Quick start

```sh
cargo build --release --manifest-path engine/Cargo.toml
engine/target/release/biorun run sequence/gc-historical.toml --workdir /tmp/gc-run
engine/target/release/biorun verify /tmp/gc-run/biorun/*-gc-historical
```

## Layout

```text
engine/                biorun (Rust): runs pipelines, records provenance
sequence/              FASTA toolkit (Python 3.10+, standard library only) + tests + bundled examples
structure/             MD scripts + crambin pipeline (needs CUDA, OpenMM, MDAnalysis)
expression/            planned
dna-models/            planned
functional-genomics/   planned
```

Each vertical keeps its own environment: the sequence toolkit needs nothing beyond Python, while structure needs a
CUDA-enabled OpenMM install. Run outputs go to a work directory outside the repository.

## Development

```sh
cargo test --manifest-path engine/Cargo.toml
(cd sequence && python3 -m unittest discover -s tests -v)
```
