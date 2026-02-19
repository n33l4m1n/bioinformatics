#!/usr/bin/env python3
"""Calculate GC content (%) of Yamanaka factor gene sequences in FASTA format."""

import sys

GENE_FILES = ["OCT4.txt", "SOX2.txt", "Klf2.txt", "c-Myc.txt"]


def calculate_gc(filepath):
    """Parse a FASTA file and return nucleotide counts and GC percentage."""
    counts = {"g": 0, "c": 0, "a": 0, "t": 0}

    with open(filepath, "r") as f:
        f.readline()  # skip FASTA header
        for line in f:
            seq = line.strip().lower()
            for nucleotide in counts:
                counts[nucleotide] += seq.count(nucleotide)

    total = sum(counts.values())
    gc_ratio = (counts["g"] + counts["c"]) / total if total > 0 else 0
    return counts, total, gc_ratio


def print_gene_results(filepath, counts, total, gc_ratio):
    """Print nucleotide breakdown and GC content for a single gene."""
    print(f"Gene: {filepath}")
    print(f"Total Base Pairs {total}")
    print(f"Guanine {counts['g']}")
    print(f"Cytosine {counts['c']}")
    print(f"Adenine {counts['a']}")
    print(f"Thymine {counts['t']}")
    print(f"{round(gc_ratio * 100, 3)}%")
    print()


if __name__ == "__main__":
    files = sys.argv[1:] if len(sys.argv) > 1 else GENE_FILES

    print("###############################################################################")
    print("Bioinformatics - Python program to calculate gc content (%) of genetic material")
    print("###############################################################################")
    print()

    gc_ratios = []
    for filepath in files:
        counts, total, gc_ratio = calculate_gc(filepath)
        print_gene_results(filepath, counts, total, gc_ratio)
        gc_ratios.append(gc_ratio)

    avg = sum(gc_ratios) / len(gc_ratios)
    print(f"Average: {round(avg * 100, 3)}%")
    print()
    print("###############################################################################")
