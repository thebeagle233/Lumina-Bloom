"""Export the shared UI as a self-contained static demo. Python standard library only."""
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "lumi-web-app"


def build_demo(output: Path | None = None) -> Path:
    output = Path(output) if output is not None else ROOT / "demo"
    output.mkdir(parents=True, exist_ok=True)
    html = (APP / "templates" / "index.html").read_text(encoding="utf-8")
    html = re.sub(
        r"\{\{\s*url_for\('static', filename='([^']+)'\)\s*\}\}",
        r"static/\1", html,
    )
    html = re.sub(
        r'<script id="runtime-config">.*?</script>',
        '<script src="static/demo-api.js"></script>', html, flags=re.S,
    )
    html = html.replace('<body>', '<body class="demo-mode">')
    html = html.replace('<!-- demo-banner -->', '''<aside class="demo-banner" role="note">
        <strong>LUMI · STATIC DEMO</strong>
        Sample weather, places &amp; history. Scripted chat. Your logs stay in this browser.
        <button id="btn-reset-demo" type="button">RESET DEMO</button>
    </aside>''')
    html = html.replace('<title>Lumina Bloom</title>', '<title>Lumi · Lumina Bloom Demo</title>')
    html = html.replace('Local companion ready.', 'Scripted demo companion.')
    if '{{' in html or '{%' in html:
        raise ValueError("Unresolved server template in static export")
    (output / "index.html").write_text(html, encoding="utf-8")
    # Copy only public assets. Backend source and environment files never enter demo/.
    shutil.copytree(APP / "static", output / "static", dirs_exist_ok=True)
    print(f"Static demo built: {output}")
    return output


if __name__ == "__main__":
    build_demo()
