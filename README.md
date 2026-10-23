# Bioinformatics Toolkit

This repository contains three related products:

1. **Sequence toolkit:** validated inputs, explicit statistics and provenance.
2. **Reprogramming and aging research:** reproducible analysis of measured cell states.
3. **Local DNA models:** small-model evaluation and bounded GPU workloads.

The sequence CLI is implemented. The research and model products are planned in
[ROADMAP.md](ROADMAP.md), with current evidence and model choices in
[FRONTIER.md](FRONTIER.md), reviewed September 30, 2026.

## Run the sequence toolkit

Requires **Python 3.10+**, with no third-party dependencies.

```sh
# Analyze the bundled historical examples; works from any directory.
python3 ~/github/bioinformatics/gc_content.py

# Analyze your own single- or multi-record DNA FASTA files.
python3 gc_content.py sequences.fa more_sequences.fasta.gz
python3 gc_content.py sequences.fa --format json > report.json
python3 gc_content.py sequences.fa --format tsv > report.tsv

# Read FASTA from standard input.
python3 gc_content.py - --format json < sequences.fa
```

The parser accepts lowercase DNA, wrapped lines, whitespace and IUPAC ambiguity
codes (`RYSWKMBDHVN`). It rejects missing/empty headers, empty records, sequence
before a header, RNA `U`, gaps, digits and other invalid symbols. Files ending
in `.gz` are decompressed. Input errors go to stderr with exit status 2; every
input is validated before any report is printed.

Sequence bases are counted line by line; the CLI retains one statistics object
per record rather than whole sequences. This is suitable for ordinary FASTA
analysis; memory still grows with the number of records and the longest line.

## What GC means here

`GC percent = 100 × (G + C) / (A + C + G + T)`

Ambiguous bases are reported separately and excluded from the denominator.
`length` includes ambiguous bases; `canonical_bases` does not. A record with no
A/C/G/T has undefined GC (`null` in JSON, `NA` in TSV), rather than zero.

Text and JSON include both the unweighted **mean of defined record percentages**
and **pooled canonical-base GC**. These answer different questions when record
lengths differ. For the bundled files they are **57.976%** and **54.423%**,
respectively. Neither value makes these mixed biological records comparable.

JSON has `schema_version: 1`, an `analysis` policy, per-record counts and
descriptions, and a `summary`. Percentages retain floating-point precision;
only text display is rounded. TSV contains one row per record, without a
summary row. The importable `calculate_gc(path)` compatibility function returns
`(lowercase_counts, canonical_total, gc_fraction)` pooled across records; the
fraction is `None` when undefined.

## Bundled data: historical examples, not a matched reference set

The original files have been preserved. Their headers identify two genomic
intervals, an mRNA and an aberrant exon:

| File | Record description | Length (nt) | GC |
| --- | --- | ---: | ---: |
| `OCT4.txt` | Human chromosome 6, GRCh38; historical OCT4/POU5F1 interval | 6,357 | 51.298% |
| `SOX2.txt` | Human chromosome 3, GRCh38; historical SOX2 interval | 2,513 | 50.696% |
| `Klf2.txt` | Human **KLF2** mRNA, `NM_016270.2` | 1,655 | 67.372% |
| `c-Myc.txt` | Human aberrant MYC exon 2 from LY67 Burkitt lymphoma cells, `X00676.1` | 961 | 62.539% |

The canonical Yamanaka factors are **OCT4/POU5F1, SOX2, KLF4 and MYC**. KLF2
must not be relabeled as KLF4. See the original
[mouse study](https://pubmed.ncbi.nlm.nih.gov/16904174/) and
[human study](https://pubmed.ncbi.nlm.nih.gov/18035408/).

[data-manifest.json](data-manifest.json) records original headers, local file
checksums, sequence counts and provenance limitations. The biological labels
come from those headers, except the OCT4/SOX2 gene labels, which come from the
filenames; their chromosome headers do not name genes. Exact sequence identity
against a newly downloaded reference has not been verified. A future matched
reference dataset will be added separately with pinned accessions, versions and
sequence types.

GC and CpG composition do not measure methylation, biological age, gene
expression or reprogramming success. Those questions require appropriate
experimental data and validated analyses.

## Development

```sh
python3 -m unittest discover -s tests -v
```

Tests cover parsing, invalid inputs, ambiguity, gzip, stdin, output formats,
aggregation, bundled sequence counts and invocation outside the repository.
No data downloads, model installations or scheduled jobs are required.
