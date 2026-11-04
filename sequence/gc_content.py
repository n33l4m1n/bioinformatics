#!/usr/bin/env python3
"""Validate DNA FASTA records and report GC content among canonical A/C/G/T bases.

IUPAC ambiguity codes are counted separately and excluded from the denominator.
GC content is undefined (None) for a record containing only ambiguous bases.
The bundled historical examples are not a canonical four-factor reference set.
"""

import argparse
from collections import Counter
import csv
from dataclasses import asdict, dataclass
import gzip
import json
from pathlib import Path
import sys
from typing import Iterator, TextIO
import zlib


GENE_FILES = ["OCT4.txt", "SOX2.txt", "Klf2.txt", "c-Myc.txt"]
CANONICAL = "ACGT"
AMBIGUOUS = "RYSWKMBDHVN"
DNA_ALPHABET = frozenset(CANONICAL + AMBIGUOUS + (CANONICAL + AMBIGUOUS).lower())


@dataclass(frozen=True)
class SequenceStats:
    source: str
    record_id: str
    description: str
    length: int
    canonical_bases: int
    ambiguous_bases: int
    counts: dict[str, int]
    ambiguity_counts: dict[str, int]

    @property
    def gc_percent(self) -> float | None:
        if not self.canonical_bases:
            return None
        return 100 * (self.counts["G"] + self.counts["C"]) / self.canonical_bases

    def to_dict(self) -> dict:
        return {**asdict(self), "gc_percent": self.gc_percent}


def _record_stats(source: str, description: str, header_line: int,
                  bases: Counter) -> SequenceStats:
    if not bases:
        raise ValueError(f"{source}:{header_line}: empty FASTA record {description!r}")
    counts = {base: bases[base] for base in CANONICAL}
    ambiguity_counts = {base: bases[base] for base in AMBIGUOUS if bases[base]}
    return SequenceStats(
        source=source,
        record_id=description.split()[0],
        description=description,
        length=sum(bases.values()),
        canonical_bases=sum(counts.values()),
        ambiguous_bases=sum(ambiguity_counts.values()),
        counts=counts,
        ambiguity_counts=ambiguity_counts,
    )


def iter_fasta(stream: TextIO, source: str = "<stream>") -> Iterator[SequenceStats]:
    """Count records line by line without storing complete sequences in memory."""
    description = None
    header_line = 0
    bases = Counter()
    for line_number, raw_line in enumerate(stream, 1):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if description is not None:
                yield _record_stats(source, description, header_line, bases)
            description = line[1:].strip()
            if not description:
                raise ValueError(f"{source}:{line_number}: empty FASTA header")
            header_line = line_number
            bases = Counter()
            continue
        if description is None:
            raise ValueError(f"{source}:{line_number}: sequence before FASTA header")
        sequence = "".join(line.split())
        invalid = set(sequence) - DNA_ALPHABET
        if invalid:
            raise ValueError(
                f"{source}:{line_number}: invalid DNA symbol(s): {', '.join(sorted(invalid))}"
            )
        bases.update(sequence.upper())
    if description is None:
        raise ValueError(f"{source}:1: no FASTA records")
    yield _record_stats(source, description, header_line, bases)


def analyze_file(filepath: str | Path) -> list[SequenceStats]:
    """Read plain or gzip-compressed DNA FASTA; '-' reads standard input."""
    if str(filepath) == "-":
        return list(iter_fasta(sys.stdin, "<stdin>"))
    path = Path(filepath)
    opener = gzip.open if path.suffix.lower() == ".gz" else open
    try:
        with opener(path, "rt", encoding="utf-8-sig") as stream:
            return list(iter_fasta(stream, str(path)))
    except (OSError, EOFError, UnicodeError, zlib.error) as error:
        raise ValueError(f"{path}: unable to read FASTA: {error}") from error


def calculate_gc(filepath: str | Path):
    """Compatibility API: lowercase counts, canonical total, GC fraction.

    Multiple records are pooled. Ambiguous bases are excluded; the fraction
    is None when no canonical bases are present. Invalid FASTA raises an error.
    """
    records = analyze_file(filepath)
    counts = {base.lower(): sum(record.counts[base] for record in records)
              for base in "GCAT"}
    total = sum(counts.values())
    fraction = (counts["g"] + counts["c"]) / total if total else None
    return counts, total, fraction


def summarize(records: list[SequenceStats]) -> dict:
    defined = [record.gc_percent for record in records if record.gc_percent is not None]
    canonical = sum(record.canonical_bases for record in records)
    gc = sum(record.counts["G"] + record.counts["C"] for record in records)
    return {
        "record_count": len(records),
        "records_with_defined_gc": len(defined),
        "length": sum(record.length for record in records),
        "canonical_bases": canonical,
        "ambiguous_bases": sum(record.ambiguous_bases for record in records),
        "mean_gc_percent": sum(defined) / len(defined) if defined else None,
        "weighted_gc_percent": 100 * gc / canonical if canonical else None,
    }


def _percent(value: float | None) -> str:
    return "undefined (no A/C/G/T bases)" if value is None else f"{value:.3f}%"


def print_gene_results(filepath, counts, total, gc_ratio):
    """Retain the original single-result display API for existing callers."""
    print(f"Gene: {filepath}\nTotal Base Pairs {total}")
    for name, base in (("Guanine", "g"), ("Cytosine", "c"),
                       ("Adenine", "a"), ("Thymine", "t")):
        print(f"{name} {counts[base]}")
    print(_percent(gc_ratio * 100 if gc_ratio is not None else None))
    print()


def write_report(records: list[SequenceStats], output_format: str) -> None:
    summary = summarize(records)
    if output_format == "json":
        json.dump({"schema_version": 1,
                   "analysis": {"gc_denominator": "canonical_bases",
                                "ambiguity_policy": "exclude"},
                   "records": [record.to_dict() for record in records],
                   "summary": summary}, sys.stdout, indent=2, allow_nan=False)
        print()
    elif output_format == "tsv":
        writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
        writer.writerow(["source", "record_id", "length", "canonical_bases",
                         "ambiguous_bases", *CANONICAL, "gc_percent"])
        for record in records:
            writer.writerow([record.source, record.record_id, record.length,
                             record.canonical_bases, record.ambiguous_bases,
                             *(record.counts[base] for base in CANONICAL),
                             record.gc_percent if record.gc_percent is not None else "NA"])
    else:
        print("GC content — denominator: canonical A/C/G/T bases\n")
        for record in records:
            print(f"File: {record.source}\nRecord: {record.description}")
            print(f"Length: {record.length}; canonical: {record.canonical_bases}; "
                  f"ambiguous: {record.ambiguous_bases}")
            print(" ".join(f"{base}: {record.counts[base]}" for base in CANONICAL))
            if record.ambiguity_counts:
                print("Ambiguities: " + " ".join(
                    f"{base}: {count}" for base, count in record.ambiguity_counts.items()))
            print(f"GC: {_percent(record.gc_percent)}\n")
        print(f"Mean record GC: {_percent(summary['mean_gc_percent'])}")
        print(f"Pooled canonical-base GC: {_percent(summary['weighted_gc_percent'])}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", metavar="FASTA",
                        help="DNA FASTA files (.gz supported); '-' for stdin; default: bundled examples")
    parser.add_argument("--format", choices=("text", "json", "tsv"), default="text",
                        help="output format (default: text)")
    args = parser.parse_args(argv)
    files = args.files or [Path(__file__).resolve().parent / name for name in GENE_FILES]
    if sum(str(path) == "-" for path in files) > 1:
        parser.error("standard input may only be used once")
    try:
        # Validate every input before printing; errors never produce a partial report.
        records = [record for path in files for record in analyze_file(path)]
    except (OSError, ValueError, UnicodeError, EOFError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    write_report(records, args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
