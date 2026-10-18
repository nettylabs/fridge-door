"""Nothing ever goes to Netty Labs or anywhere else: the toolkit must not import any networking module.

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
}


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


if __name__ == "__main__":
    unittest.main()
