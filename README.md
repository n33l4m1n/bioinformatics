# Bioinformatics

A Python program that calculates the GC content (guanine-cytosine percentage) of the four Yamanaka factor genes used to reprogram somatic cells into induced pluripotent stem cells (iPSCs).

## Background

The iPSC technology was pioneered by Shinya Yamanaka's lab in Kyoto, Japan. In 2006, Yamanaka demonstrated that four specific transcription factors could convert somatic cells into pluripotent stem cells. He was awarded the 2012 Nobel Prize along with Sir John Gurdon for the discovery that "mature cells can be reprogrammed to become pluripotent."

## Genes Analyzed

Gene sequences are in FASTA format sourced from NCBI GenBank.

| Gene | Description | GC Content |
|------|-------------|------------|
| OCT4 (POU5F1) | Human chromosome 6, GRCh38 Primary Assembly | 51.298% |
| SOX2 | Human chromosome 3, GRCh38 Primary Assembly | 50.696% |
| Klf2 (KLF2) | Homo sapiens Kruppel-like factor 2, mRNA | 67.372% |
| c-Myc | Human aberrant c-myc exon 2, Burkitt lymphoma | 62.539% |

## Usage

```sh
python gc_content.py
```

## Sample Output

```
Gene: OCT4.txt
Total Base Pairs 6357
Guanine 1660
Cytosine 1601
Adenine 1470
Thymine 1626
51.298%

...

Average: 57.976%
```
