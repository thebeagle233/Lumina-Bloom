"""Verify the deployable demo contains real assets, with no server templates."""
from pathlib import Path
import runpy
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BuildDemoTests(unittest.TestCase):
    def test_export_works_from_any_directory_without_flask(self):
        builder = runpy.run_path(str(ROOT / "scripts" / "build_demo.py"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "public"
            builder["build_demo"](target)
            html = (target / "index.html").read_text()
            self.assertNotIn("{{", html)
            self.assertNotIn("{%", html)
            self.assertIn("STATIC DEMO", html)
            self.assertIn('src="static/demo-api.js"', html)
            self.assertIn('href="static/styles.css"', html)
            self.assertLess(html.index("static/demo-api.js"), html.index("static/app.js"))
            for name in ("app.js", "styles.css", "demo-api.js"):
                self.assertTrue((target / "static" / name).is_file())
            self.assertFalse(list(target.rglob("*.py")))
            self.assertFalse(list(target.rglob(".env*")))
            before = {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()}
            builder["build_demo"](target)
            after = {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
