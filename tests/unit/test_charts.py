"""Reuso de gráficos com fixtures neutras; sem avaliação de modelo."""
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from medassistmultimodal.infrastructure.charts import write_bar_chart, write_grouped_chart


class ChartsTests(unittest.TestCase):
    def test_svg_preserves_numeric_data_and_escapes_labels(self):
        rows = [{"label": "Fixture <A> & B", "score": 0.75, "latency_ms": 12.0}]
        with tempfile.TemporaryDirectory() as directory:
            grouped = Path(directory) / "grouped.svg"
            bars = Path(directory) / "bars.svg"
            write_grouped_chart(grouped, rows, (("score", "Score", "#2563EB"),),
                                "Fixture", "Score", 1.0)
            write_bar_chart(bars, rows, "latency_ms", "Latência", "Fixture", "ms")
            for path in (grouped, bars):
                svg = ET.parse(path).getroot()
                self.assertEqual(svg.tag, "{http://www.w3.org/2000/svg}svg")
                self.assertIn("Fixture <A> & B", "".join(svg.itertext()))
            self.assertIn("0.750", grouped.read_text(encoding="utf-8"))
