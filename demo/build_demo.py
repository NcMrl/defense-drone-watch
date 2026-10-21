"""Génère demo/index.html (page de démonstration autonome) à partir d'un export JSON des données synthétiques."""
import json
import sys
from pathlib import Path

here = Path(__file__).parent
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert all(d["is_synthetic"] for d in data["documents"]), "La démo ne doit contenir que des données synthétiques"
payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
html = (here / "template.html").read_text(encoding="utf-8").replace("__DATA__", payload)
(here / "index.html").write_text(html, encoding="utf-8")
print(f"index.html : {len(html)} octets, {len(data['documents'])} documents")
