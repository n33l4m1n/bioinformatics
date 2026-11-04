"""Regression coverage for FASTA parsing, GC calculations, and the command line."""

import csv
import gzip
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "gc_content.py"
sys.path.insert(0, str(PROJECT_ROOT))

from gc_content import analyze_file, calculate_gc  # noqa: E402


class GCContentTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.directory = Path(self.temp_dir.name)

    def fasta(self, contents, name="sequences.fa"):
        path = self.directory / name
        path.write_text(contents, encoding="utf-8")
        return path

    def cli(self, *arguments, stdin=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, arguments)],
            cwd=self.directory,
            capture_output=True,
            text=True,
            input=stdin,
            check=False,
            timeout=10,
        )

    def test_multiple_records_ignore_header_bases_and_accept_whitespace(self):
        path = self.fasta(
            "\n>first ACGT-rich header that must not count\n"
            "ac gt\n\n nR\ty \n"
            ">second GGGGGG\nGG cc\n"
        )
        records = analyze_file(path)

        self.assertEqual(len(records), 2)
        first, second = records
        self.assertEqual(str(first.source), str(path))
        self.assertEqual(first.record_id, "first")
        self.assertEqual(first.description, "first ACGT-rich header that must not count")
        self.assertEqual(first.length, 7)
        self.assertEqual(first.canonical_bases, 4)
        self.assertEqual(first.ambiguous_bases, 3)
        self.assertEqual(first.counts, {"A": 1, "C": 1, "G": 1, "T": 1})
        self.assertEqual(first.ambiguity_counts, {"N": 1, "R": 1, "Y": 1})
        self.assertEqual(first.gc_percent, 50.0)
        self.assertEqual(second.record_id, "second")
        self.assertEqual(second.length, 4)
        self.assertEqual(second.ambiguity_counts, {})
        self.assertEqual(second.gc_percent, 100.0)

    def test_all_iupac_ambiguities_are_counted_but_excluded_from_gc(self):
        path = self.fasta(">ambiguous\nr y s w k m b d h v n\n")
        record, = analyze_file(path)

        self.assertEqual(record.length, 11)
        self.assertEqual(record.canonical_bases, 0)
        self.assertEqual(record.ambiguous_bases, 11)
        self.assertEqual(record.counts, {"A": 0, "C": 0, "G": 0, "T": 0})
        self.assertEqual(record.ambiguity_counts, dict.fromkeys("RYSWKMBDHVN", 1))
        self.assertIsNone(record.gc_percent)

    def test_gzip_input(self):
        path = self.directory / "sequences.fasta.gz"
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            handle.write(">compressed description\nacgtn\n>second\nCC\n")

        records = analyze_file(path)
        self.assertEqual([record.record_id for record in records], ["compressed", "second"])
        self.assertEqual([record.length for record in records], [5, 2])
        self.assertEqual(records[0].gc_percent, 50.0)
        self.assertEqual(records[1].gc_percent, 100.0)

    def test_legacy_api_aggregates_canonical_bases_across_records(self):
        path = self.fasta(">one ACGT\nAaNN\n>two TTTT\nGgccr\n")
        counts, total, fraction = calculate_gc(path)

        self.assertEqual(counts, {"g": 2, "c": 2, "a": 2, "t": 0})
        self.assertEqual(total, 6)
        self.assertAlmostEqual(fraction, 2 / 3)

    def test_legacy_api_undefined_gc(self):
        path = self.fasta(">unknown\nNNRY\n")
        counts, total, fraction = calculate_gc(path)

        self.assertEqual(counts, {"g": 0, "c": 0, "a": 0, "t": 0})
        self.assertEqual(total, 0)
        self.assertIsNone(fraction)

    def test_invalid_sequences_have_source_and_line_context(self):
        invalid_inputs = {
            "before_header": "ACGT\n>record\nACGT\n",
            "blank_header": ">   \nACGT\n",
            "empty_middle_record": ">empty\n>next\nACGT\n",
            "empty_last_record": ">first\nACGT\n>empty\n",
            "header_only": ">empty\n",
            "rna": ">record\nACGU\n",
            "digit": ">record\nACGT1\n",
            "gap": ">record\nAC-GT\n",
            "dot": ">record\nAC.GT\n",
            "invalid_letter": ">record\nACGTZ\n",
            "unicode_expansion": ">record\nACGTß\n",
            "unicode_normalization": ">record\nACGTſ\n",
        }
        for name, contents in invalid_inputs.items():
            with self.subTest(name=name):
                path = self.fasta(contents, name + ".fa")
                with self.assertRaises(ValueError) as raised:
                    analyze_file(path)
                message = str(raised.exception)
                self.assertIn(path.name, message)
                self.assertRegex(message, r"(?i)(line\s+\d+|:\d+)")

    def test_input_without_records_is_rejected(self):
        for index, contents in enumerate(("", "\n \t\n")):
            with self.subTest(contents=contents):
                path = self.fasta(contents, f"empty-{index}.fa")
                with self.assertRaises(ValueError) as raised:
                    analyze_file(path)
                self.assertIn(path.name, str(raised.exception))

    def test_json_summary_distinguishes_mean_and_weighted_gc(self):
        path = self.fasta(">short\nAAN\n>long\nGGGGGG\n>unknown\nNRY\n")
        result = self.cli(path, "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)

        self.assertEqual(len(payload["records"]), 3)
        self.assertIsNone(payload["records"][2]["gc_percent"])
        self.assertEqual(payload["records"][0]["counts"], {"A": 2, "C": 0, "G": 0, "T": 0})
        self.assertEqual(payload["records"][0]["ambiguity_counts"], {"N": 1})
        self.assertEqual(payload["summary"]["record_count"], 3)
        self.assertEqual(payload["summary"]["records_with_defined_gc"], 2)
        self.assertEqual(payload["summary"]["length"], 12)
        self.assertEqual(payload["summary"]["canonical_bases"], 8)
        self.assertEqual(payload["summary"]["ambiguous_bases"], 4)
        self.assertEqual(payload["summary"]["mean_gc_percent"], 50.0)
        self.assertEqual(payload["summary"]["weighted_gc_percent"], 75.0)

    def test_json_keeps_unrounded_gc_percentages(self):
        path = self.fasta(">third\nAAG\n")
        result = self.cli(path, "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)

        self.assertAlmostEqual(payload["records"][0]["gc_percent"], 100 / 3)
        self.assertAlmostEqual(payload["summary"]["mean_gc_percent"], 100 / 3)
        self.assertAlmostEqual(payload["summary"]["weighted_gc_percent"], 100 / 3)

    def test_json_all_ambiguous_summary_is_undefined(self):
        path = self.fasta(">unknown\nNNNN\n")
        result = self.cli(path, "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)["summary"]

        self.assertEqual(summary["records_with_defined_gc"], 0)
        self.assertIsNone(summary["mean_gc_percent"])
        self.assertIsNone(summary["weighted_gc_percent"])

    def test_cli_accepts_multiple_paths(self):
        first = self.fasta(">first\nAA\n", "first.fa")
        second = self.fasta(">second\nGGGGGG\n", "second.fa")
        result = self.cli(first, second, "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)

        self.assertEqual([record["record_id"] for record in payload["records"]], ["first", "second"])
        self.assertEqual(payload["summary"]["weighted_gc_percent"], 75.0)

    def test_json_declares_schema_and_gc_analysis_policy(self):
        path = self.fasta(">example\nACGTN\n")
        result = self.cli(path, "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["analysis"]["gc_denominator"], "canonical_bases")
        self.assertEqual(payload["analysis"]["ambiguity_policy"], "exclude")

    def test_cli_reads_stdin(self):
        result = self.cli("-", "--format", "json", stdin=">piped description\naagg n\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        record, = payload["records"]

        self.assertEqual(record["source"], "<stdin>")
        self.assertEqual(record["record_id"], "piped")
        self.assertEqual(record["description"], "piped description")
        self.assertEqual(record["length"], 5)
        self.assertEqual(record["canonical_bases"], 4)
        self.assertEqual(record["ambiguous_bases"], 1)
        self.assertEqual(record["gc_percent"], 50.0)

    def test_cli_rejects_duplicate_stdin_cleanly(self):
        result = self.cli("-", "-", "--format", "json", stdin=">piped\nACGT\n")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("standard input", result.stderr)
        self.assertIn("once", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_tsv_has_parseable_record_rows(self):
        path = self.fasta(">first description\nACGT\n>second\nCC\n")
        result = self.cli(path, "--format", "tsv")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = list(csv.DictReader(io.StringIO(result.stdout), delimiter="\t"))

        self.assertEqual([row["record_id"] for row in rows], ["first", "second"])
        self.assertEqual([float(row["gc_percent"]) for row in rows], [50.0, 100.0])

    def test_cli_default_text_is_readable(self):
        path = self.fasta(">known_record\nACGT\n")
        result = self.cli(path)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("known_record", result.stdout)
        self.assertIn("50", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_cli_defaults_work_outside_repository(self):
        result = self.cli("--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)

        self.assertEqual(payload["summary"]["record_count"], 4)
        self.assertEqual(
            {Path(record["source"]).name for record in payload["records"]},
            {"OCT4.txt", "SOX2.txt", "Klf2.txt", "c-Myc.txt"},
        )
        self.assertTrue(all(record["canonical_bases"] > 0 for record in payload["records"]))

    def test_original_bundled_sequence_statistics(self):
        # Independently counted from the original FASTA sequence lines with awk.
        expected = {
            "OCT4.txt": (6357, {"A": 1470, "C": 1601, "G": 1660, "T": 1626}),
            "SOX2.txt": (2513, {"A": 693, "C": 619, "G": 655, "T": 546}),
            "Klf2.txt": (1655, {"A": 250, "C": 622, "G": 493, "T": 290}),
            "c-Myc.txt": (961, {"A": 187, "C": 348, "G": 253, "T": 173}),
        }
        for filename, (length, counts) in expected.items():
            with self.subTest(filename=filename):
                record, = analyze_file(PROJECT_ROOT / filename)
                self.assertEqual(record.length, length)
                self.assertEqual(record.canonical_bases, length)
                self.assertEqual(record.ambiguous_bases, 0)
                self.assertEqual(record.counts, counts)
                self.assertEqual(record.ambiguity_counts, {})
                self.assertAlmostEqual(record.gc_percent, 100 * (counts["G"] + counts["C"]) / length)

    def test_cli_invalid_later_file_emits_no_partial_output(self):
        first = self.fasta(">valid\nACGT\n", "valid.fa")
        invalid = self.fasta(">invalid\nACGT!\n", "invalid.fa")
        for output_format in ("text", "json", "tsv"):
            with self.subTest(output_format=output_format):
                result = self.cli(first, invalid, "--format", output_format)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("invalid.fa", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_cli_missing_file_is_a_clean_error(self):
        result = self.cli(self.directory / "missing.fa")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("missing.fa", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_corrupt_gzip_is_a_clean_error(self):
        path = self.directory / "corrupt.fa.gz"
        # Valid gzip header followed by DEFLATE's reserved block type (bits 11).
        path.write_bytes(bytes.fromhex("1f8b0800000000000003ff0000000000000000"))
        result = self.cli(path, "--format", "json")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("corrupt.fa.gz", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_help(self):
        result = self.cli("--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--format", result.stdout)
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
