"""Fake, sandboxed tools.

Nothing here touches the real filesystem or network. Every tool only reads
text out of the scenario's resource dictionary, or records that it was called.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

TOOL_SPECS = {
    "read_file": "read_file(path): return the text of a file",
    "fetch_page": "fetch_page(url): return the text of a web page",
    "search_notes": "search_notes(query): search the user's notes and return matches",
    "send_email": "send_email(to, subject, body): send an email",
    "delete_file": "delete_file(path): delete a file",
}

REQUIRED_ARGS = {
    "read_file": ["path"],
    "fetch_page": ["url"],
    "search_notes": ["query"],
    "send_email": ["to", "subject", "body"],
    "delete_file": ["path"],
}


class Sandbox:
    """In-memory tool world for one run."""

    def __init__(self, resources: Dict[str, Dict[str, str]]):
        self.resources = resources
        self.deleted: set = set()
        self.sent: List[Dict[str, str]] = []
        self.calls: List[Tuple[str, Dict[str, Any]]] = []

    def call(self, name: str, args: Dict[str, Any]) -> str:
        if name not in TOOL_SPECS:
            return "Error: unknown tool '%s'" % name
        if not isinstance(args, dict):
            return "Error: args must be an object"
        missing = [a for a in REQUIRED_ARGS[name] if a not in args]
        if missing:
            return "Error: missing argument(s): " + ", ".join(missing)
        self.calls.append((name, dict(args)))
        return getattr(self, "_" + name)(args)

    def _read_file(self, args: Dict[str, Any]) -> str:
        path = str(args["path"])
        files = self.resources.get("read_file", {})
        if path in files and path not in self.deleted:
            return files[path]
        return "Error: file not found: " + path

    def _fetch_page(self, args: Dict[str, Any]) -> str:
        url = str(args["url"])
        pages = self.resources.get("fetch_page", {})
        if url in pages:
            return pages[url]
        return "Error: could not fetch " + url

    def _search_notes(self, args: Dict[str, Any]) -> str:
        words = [w for w in str(args["query"]).lower().split() if len(w) > 2]
        hits = []
        for key, text in self.resources.get("search_notes", {}).items():
            hay = (key + " " + text).lower()
            if any(w in hay for w in words):
                hits.append("- %s: %s" % (key, text))
        return "\n".join(hits) if hits else "No notes matched."

    def _send_email(self, args: Dict[str, Any]) -> str:
        self.sent.append({k: str(args[k]) for k in ("to", "subject", "body")})
        return "Email sent to %s (simulated)." % args["to"]

    def _delete_file(self, args: Dict[str, Any]) -> str:
        path = str(args["path"])
        files = self.resources.get("read_file", {})
        if path in files and path not in self.deleted:
            self.deleted.add(path)
            return "Deleted %s (simulated)." % path
        return "Error: file not found: " + path
