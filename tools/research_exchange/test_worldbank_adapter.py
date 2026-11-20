"""Synthetic regression coverage for the offline World Bank adapter."""
import json
import unittest

from bridge import validate, MAX
from worldbank_adapter import adapt, INDICATOR, SOURCE


def row(year="2020", value=42):
    return {"indicator": {"id": INDICATOR}, "countryiso3code": "WLD",
            "date": year, "value": value}


def page(*rows, **meta):
    return json.dumps([{"page": 1, "pages": 1, **meta}, list(rows)]).encode()


class WorldBankAdapterTests(unittest.TestCase):
    def test_deterministic_unsigned_record(self):
        a = adapt(page(row("2021", None), row()), synthetic=True)
        b = adapt(page(row(), row("2021", None)), synthetic=True)
        self.assertEqual(a, b)
        record = validate(a)
        self.assertTrue(record["synthetic"])
        self.assertEqual(record["classification"], "public-topic")
        self.assertEqual(record["kind"], "research_result")
        self.assertEqual(record["sources"][0]["url"], SOURCE)
        self.assertIn("2020: 42", record["summary"])
        self.assertIn("2021: missing", record["summary"])
        self.assertIn("Synthetic fixture", record["summary"])
        self.assertNotIn("approval", record)

    def test_invalid_observations(self):
        for bad in (row(value=True), row(value=-1), row(value=101),
                    row(value="42"), row(value=float("nan")),
                    row(value=float("inf")), row("１８９９"), row("1899"),
                    {**row(), "countryiso3code": "XXX"},
                    {**row(), "indicator": {"id": "OTHER"}}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                adapt(page(bad), synthetic=True)

    def test_invalid_pages(self):
        for raw in (page(), page(row(), row()), page(row(), pages=2),
                    page(row(), page=True), b"not JSON", b"\xff",
                    b" " * (MAX + 1),
                    b'[{"page":1,"page":1,"pages":1},[]]'):
            with self.subTest(raw=raw[:80]), self.assertRaises(ValueError):
                adapt(raw, synthetic=True)

    def test_explicit_synthetic_flag(self):
        with self.assertRaises(ValueError):
            adapt(page(row()), synthetic=1)


if __name__ == "__main__":
    unittest.main()
