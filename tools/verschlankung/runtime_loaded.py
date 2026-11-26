import sys, os, json
sys.path[:0] = ["src", ".", "PersonOSINT"]
os.environ["LOCALAPPDATA"] = sys.argv[2]
from eagleeye.interfaces.web.app500 import create_workspace_app500
app = create_workspace_app500(base_dir=sys.argv[2] + "/ws")
import eagleeye.bootstrap.desktop476, eagleeye.bootstrap.windows_start, eagleeye.interfaces.cli.main
import personosint.__main__  # noqa
from personosint.vault_app import create_vault_app
try:
    create_vault_app(sys.argv[2] + "/vault")
except Exception as e:
    print("vault", type(e).__name__, e)
loaded = sorted(n for n, m in sys.modules.items() if n.split(".")[0] in ("eagleeye", "eagleeye_pro", "personosint") and getattr(m, "__file__", None))
apps = sorted(n.rsplit("app", 1)[1] for n in loaded if n.startswith("eagleeye.interfaces.web.app") and n.rsplit("app", 1)[1].isdigit())
print("loaded", len(loaded), "app chain", apps[0], "..", apps[-1], len(apps))
json.dump({"loaded": loaded, "routes": [(getattr(r, "path", ""), sorted(getattr(r, "methods", None) or []), getattr(getattr(r, "endpoint", None), "__module__", ""), getattr(getattr(r, "endpoint", None), "__qualname__", "")) for r in app.routes]}, open(sys.argv[1], "w"))
