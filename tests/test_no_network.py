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
    "_socket",
    "ssl",
    "_ssl",
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
    "logging.handlers",  # socket, HTTP and email log handlers
    "wsgiref",
    "pydoc",  # has a web server
    "pty",
    "_posixsubprocess",
    "concurrent",  # process pools
    "runpy",
    "pkgutil",
    "zipimport",
    "builtins",
}
# The one place that may start another program: the optional browser printer for scripts the built-in PDF fonts
# can't show (SECURITY.md). It runs a browser already on the computer, offline, on a local file.
PROCESS_ALLOWED = {"fridgedoor/render.py"}
OS_PROCESS_CALLS = {"system", "popen", "startfile", "fork", "forkpty", "posix_spawn", "posix_spawnp"}


def _imported(node) -> list:
    """Every module (and "module.name" for from-imports) a node imports."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
        return [node.module] + [f"{node.module}.{alias.name}" for alias in node.names]
    return []


def _forbidden(name: str) -> bool:
    parts = name.split(".")
    return any(".".join(parts[:i]) in FORBIDDEN for i in range(1, len(parts) + 1))


def _os_process_call(name: str) -> bool:
    return name in OS_PROCESS_CALLS or name.startswith(("exec", "spawn"))


class NoNetworkTest(unittest.TestCase):
    def test_no_networking_imports(self):
        offenders = []
        for path in sorted(SCRIPTS.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names = _imported(node)
                if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "__import__":
                    names = ["__import__"]
                for name in names:
                    if _forbidden(name) or name == "__import__":
                        offenders.append(f"{path.relative_to(SCRIPTS)}:{node.lineno} imports {name}")
        self.assertEqual(offenders, [], "networking code found")

    def test_no_dynamic_imports_or_code(self):
        offenders = []
        for path in sorted(SCRIPTS.rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
                if not isinstance(node, ast.Call):
                    continue
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                builtin = getattr(node.func, "id", None)  # compile() itself, not re.compile()
                first = getattr(node.args[0], "id", "") if node.args else ""
                if (name in ("__import__", "eval", "exec", "import_module") or builtin == "compile"
                        or (builtin == "getattr" and first in ("__builtins__", "builtins", "os"))):
                    offenders.append(f"{path.relative_to(SCRIPTS)}:{node.lineno} calls {name}")
        self.assertEqual(offenders, [], "dynamic imports or code found")

    def test_only_the_browser_printer_runs_another_program(self):
        offenders = []
        for path in sorted(SCRIPTS.rglob("*.py")):
            rel = path.relative_to(SCRIPTS).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            os_names = {"os"} | {alias.asname for node in ast.walk(tree) if isinstance(node, ast.Import)
                                 for alias in node.names if alias.name == "os" and alias.asname}  # fmt: skip
            for node in ast.walk(tree):
                names = _imported(node)
                if "subprocess" in {n.split(".")[0] for n in names} and rel not in PROCESS_ALLOWED:
                    offenders.append(f"{rel}:{node.lineno} imports subprocess")
                if any(n.startswith("os.") and _os_process_call(n[3:]) for n in names):  # from os import system
                    offenders.append(f"{rel}:{node.lineno} imports a process call from os")
                func = getattr(node, "func", None)
                if (isinstance(node, ast.Call) and isinstance(func, ast.Attribute)
                        and getattr(func.value, "id", "") in os_names and _os_process_call(func.attr)):
                    offenders.append(f"{rel}:{node.lineno} calls os.{func.attr}")
        self.assertEqual(offenders, [], "a program started outside the browser printer")
        render = (SCRIPTS / "fridgedoor" / "render.py").read_text(encoding="utf-8")
        for flag in ("--disable-background-networking", "--disable-sync", "--disable-extensions", "--user-data-dir"):
            self.assertIn(flag, render)  # offline, with a throwaway profile
        self.assertIn("html_file.as_uri()", render)  # and only ever a local file


if __name__ == "__main__":
    unittest.main()
