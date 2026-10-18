"""Nothing ever goes to Netty Labs or anywhere else: the toolkit must not import any networking module, load code
dynamically, or start another program (apart from the optional local browser printer).

This keeps the promise in the README and SECURITY.md checkable. Adding a network feature means a fresh privacy
and legal review first (see the README's "For parents" section).
"""

import ast
import unittest

from helpers import SCRIPTS

FORBIDDEN = {
    "socket",
    "ssl",
    "http",
    "urllib",
    "urllib2",
    "urllib3",
    "requests",
    "httpx",
    "aiohttp",
    "ftplib",
    "smtplib",
    "poplib",
    "imaplib",
    "telnetlib",
    "xmlrpc",
    "socketserver",
    "asyncio",
    "webbrowser",
    "ctypes",
    "multiprocessing",
    "importlib",
}
# The one place that may start another program: the optional browser printer for scripts the built-in PDF fonts
# can't show (SECURITY.md). It runs a browser already on the computer, offline, on a local file.
PROCESS_ALLOWED = {"fridgedoor/render.py"}
OS_PROCESS_CALLS = {"system", "popen", "startfile", "fork", "forkpty", "posix_spawn", "posix_spawnp"}


class NoNetworkTest(unittest.TestCase):
    def test_no_networking_imports(self):
        offenders = []
        for path in sorted(SCRIPTS.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    names = [node.module]
                elif isinstance(node, ast.Call) and getattr(node.func, "id", "") == "__import__":
                    names = ["__import__"]
                for name in names:
                    if name.split(".")[0] in FORBIDDEN or name == "__import__":
                        offenders.append(f"{path.relative_to(SCRIPTS)}:{node.lineno} imports {name}")
        self.assertEqual(offenders, [], "networking code found")

    def test_no_dynamic_imports_or_code(self):
        offenders = []
        for path in sorted(SCRIPTS.rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
                if not isinstance(node, ast.Call):
                    continue
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name in ("__import__", "eval", "exec", "import_module"):
                    offenders.append(f"{path.relative_to(SCRIPTS)}:{node.lineno} calls {name}")
        self.assertEqual(offenders, [], "dynamic imports or code found")

    def test_only_the_browser_printer_runs_another_program(self):
        offenders = []
        for path in sorted(SCRIPTS.rglob("*.py")):
            rel = path.relative_to(SCRIPTS).as_posix()
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module or ""]
                else:
                    names = []
                if "subprocess" in {n.split(".")[0] for n in names} and rel not in PROCESS_ALLOWED:
                    offenders.append(f"{rel}:{node.lineno} imports subprocess")
                func = getattr(node, "func", None)
                if (isinstance(node, ast.Call) and isinstance(func, ast.Attribute) and getattr(func.value, "id", "")
                        == "os" and (func.attr in OS_PROCESS_CALLS or func.attr.startswith(("exec", "spawn")))):
                    offenders.append(f"{rel}:{node.lineno} calls os.{func.attr}")
        self.assertEqual(offenders, [], "a program started outside the browser printer")
        render = (SCRIPTS / "fridgedoor" / "render.py").read_text(encoding="utf-8")
        for flag in ("--disable-background-networking", "--disable-sync", "--disable-extensions", "--user-data-dir"):
            self.assertIn(flag, render)  # offline, with a throwaway profile
        self.assertIn("html_file.as_uri()", render)  # and only ever a local file


if __name__ == "__main__":
    unittest.main()
