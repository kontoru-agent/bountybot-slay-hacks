"""Program scope model: what is in scope, what is already known, what pays.

A scope file is the contract between the hunter and the program. Anything
outside it is not a finding, and anything on the known-issues list is a
duplicate by definition — checking it first is what keeps the agent from
wasting a program's time.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class KnownIssue:
    id: str
    title: str
    status: str


@dataclass
class Scope:
    program: str
    version: str
    in_scope: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    known_issues: list[KnownIssue] = field(default_factory=list)
    reward_tiers: dict[str, int] = field(default_factory=dict)
    notes: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Scope":
        data = json.loads(Path(path).read_text())
        return cls(
            program=data.get("program", "?"),
            version=data.get("version", "?"),
            in_scope=list(data.get("in_scope", [])),
            out_of_scope=list(data.get("out_of_scope", [])),
            known_issues=[
                KnownIssue(str(k.get("id", "?")), str(k.get("title", "")),
                           str(k.get("status", "")))
                for k in data.get("known_issues", [])
            ],
            reward_tiers={str(k): int(v) for k, v in data.get("reward_tiers", {}).items()},
            notes=str(data.get("notes", "")),
        )

    def is_in_scope(self, rel_path: str) -> bool:
        """True when a relative file path is inside the declared scope."""
        return any(rel_path == p or rel_path.startswith(p.rstrip("*"))
                   for p in self.in_scope)

    def matches_known_issue(self, title: str, keywords: list[str]) -> KnownIssue | None:
        """Return the known issue whose title shares a keyword, else None."""
        hay = title.lower()
        for issue in self.known_issues:
            text = issue.title.lower()
            if any(kw.lower() in text or kw.lower() in hay for kw in keywords):
                # Only a real match counts: the keyword must appear in BOTH
                # the candidate title and the known-issue title.
                if any(kw.lower() in text for kw in keywords) and \
                   any(kw.lower() in hay for kw in keywords):
                    return issue
        return None
