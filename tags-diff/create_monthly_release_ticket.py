#!/usr/bin/env python3
"""Create a Monthly Release issue in Linear from template + grouped tickets."""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

LINEAR_API_URL = "https://api.linear.app/graphql"


@dataclass
class MonthlyTicketConfig:
    """Inputs for creating the monthly release Linear issue (Step 4 of the release pipeline)."""

    input_path: Path
    api_key: Optional[str] = None
    template_name: str = "Monthly Release"
    template_id: str = ""
    assignee_query: str = "gaurav"
    team_key: str = "HZ"
    team_id: str = ""
    title: str = ""
    month_label: str = ""
    dry_run: bool = False


# process_all_repos.py formats all_tickets as: "TICKET-ID : status : title"
_TICKET_WITH_META = re.compile(r"^(\S+)\s*:\s*(.+?)\s*:\s*(.+)$", re.DOTALL)
_TICKET_ID_ONLY = re.compile(r"^([A-Za-z]+-\d+)$")


def parse_ticket_line(line: str) -> tuple[str, str]:
    """Return (ticket_id, summary). Summary is title from Linear when line includes status/title."""
    s = (line or "").strip()
    if not s:
        return "", ""
    m = _TICKET_WITH_META.match(s)
    if m:
        return m.group(1).strip(), m.group(3).strip()
    m2 = _TICKET_ID_ONLY.match(s)
    if m2:
        return m2.group(1), ""
    return s, ""


def ticket_summaries_from_all_tickets(data: Dict[str, Any]) -> Dict[str, str]:
    """Map ticket id -> title/summary from `all_tickets` strings (see process_all_repos)."""
    out: Dict[str, str] = {}
    raw = data.get("all_tickets")
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, str):
            continue
        tid, summary = parse_ticket_line(item)
        if tid:
            out[tid] = summary
    return out


# Linear API returns project.state; active work is typically "started" (UI: In Progress).
IN_PROGRESS_PROJECT_STATES = frozenset({"started"})


def linear_projects_in_progress(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Subset of `projects` from final_tag_differences.json where state is in progress."""
    raw = data.get("projects")
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        st = str(p.get("state", "")).strip().lower()
        if st in IN_PROGRESS_PROJECT_STATES:
            out.append(p)
    return sorted(out, key=lambda x: str(x.get("name", "") or "").lower())


def linear_request(api_key: str, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    payload: Dict[str, Any] = {"query": query}
    if variables is not None:
        payload["variables"] = variables

    resp = requests.post(LINEAR_API_URL, headers=headers, json=payload, timeout=30)
    try:
        data = resp.json()
    except ValueError:
        data = None

    if resp.status_code >= 400:
        if isinstance(data, dict) and data.get("errors"):
            messages = "; ".join(e.get("message", "Unknown error") for e in data["errors"])
            raise RuntimeError(f"Linear API HTTP {resp.status_code}: {messages}")
        raise RuntimeError(f"Linear API HTTP {resp.status_code}: {resp.text[:800]}")

    if isinstance(data, dict) and data.get("errors"):
        messages = "; ".join(e.get("message", "Unknown error") for e in data["errors"])
        raise RuntimeError(f"Linear API error: {messages}")
    return data.get("data", {}) if isinstance(data, dict) else {}


def read_grouped_tickets(input_path: Path) -> Dict[str, List[str]]:
    grouped, _, _ = load_release_data(input_path)
    return grouped


def load_release_data(
    input_path: Path,
) -> tuple[Dict[str, List[str]], Dict[str, str], List[Dict[str, Any]]]:
    """Load tickets_by_project, all_tickets summaries, and in-progress Linear projects."""
    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    summaries = ticket_summaries_from_all_tickets(data)
    projects_ip = linear_projects_in_progress(data)

    grouped = data.get("tickets_by_project")
    if isinstance(grouped, dict) and grouped:
        out: Dict[str, List[str]] = {}
        for k, v in grouped.items():
            if isinstance(v, list):
                out[k] = sorted(set(str(x) for x in v if x))
        return dict(sorted(out.items(), key=lambda kv: kv[0])), summaries, projects_ip

    derived: Dict[str, List[str]] = {}
    all_tickets = data.get("all_tickets", [])
    if isinstance(all_tickets, list):
        for item in all_tickets:
            ticket = str(item).split(":", 1)[0].strip()
            if "-" in ticket:
                proj = ticket.split("-", 1)[0]
                derived.setdefault(proj, []).append(ticket)

    if not derived and isinstance(data.get("services"), list):
        for service in data["services"]:
            for t in service.get("tickets", []):
                ticket = str(t)
                if "-" in ticket:
                    proj = ticket.split("-", 1)[0]
                    derived.setdefault(proj, []).append(ticket)

    for proj in list(derived.keys()):
        derived[proj] = sorted(set(derived[proj]))
    return dict(sorted(derived.items(), key=lambda kv: kv[0])), summaries, projects_ip


# Project prefixes grouped for Linear mentions in the monthly summary body
SECTION_ABHISHES_PROJECTS = ("AE", "PLAT")
SECTION_GAURAV_PROJECTS = ("CLOUD", "DPP")


def _append_project_tickets(
    lines: List[str],
    project: str,
    tickets: List[str],
    id_to_summary: Dict[str, str],
) -> None:
    if not tickets:
        return
    lines.append(f"### {project} ({len(tickets)})")
    for tid in tickets:
        summ = id_to_summary.get(tid, "").strip()
        if summ:
            lines.append(f"- `{tid}` — {summ}")
        else:
            lines.append(f"- `{tid}`")
    lines.append("")


def _append_linear_projects_in_progress(lines: List[str], projects: List[Dict[str, Any]]) -> None:
    if not projects:
        return
    lines.append("## Projects — In Progress")
    lines.append("")
    for p in projects:
        name = str(p.get("name") or "Untitled").strip() or "Untitled"
        url = str(p.get("url") or "").strip()
        desc = str(p.get("description") or "").strip()
        prog = p.get("progress")
        pct_s = ""
        if isinstance(prog, (int, float)):
            pct_s = f"{prog * 100:.0f}%"
        head = f"- [{name}]({url})" if url else f"- **{name}**"
        if pct_s:
            head = f"{head} — {pct_s}"
        lines.append(head)
        if desc:
            lines.append(f"  {desc}")
    lines.append("")


def build_summary(
    grouped: Dict[str, List[str]],
    month_label: str,
    id_to_summary: Optional[Dict[str, str]] = None,
    in_progress_projects: Optional[List[Dict[str, Any]]] = None,
) -> str:
    id_to_summary = id_to_summary or {}
    in_progress_projects = in_progress_projects or []
    total = sum(len(v) for v in grouped.values())
    lines = [
        f"Monthly release summary for {month_label}.",
        "",
        f"Total unique tickets: {total}",
        "",
    ]

    _append_linear_projects_in_progress(lines, in_progress_projects)

    ab_set = set(SECTION_ABHISHES_PROJECTS)
    g_set = set(SECTION_GAURAV_PROJECTS)

    ab_keys = [p for p in SECTION_ABHISHES_PROJECTS if grouped.get(p)]
    g_keys = [p for p in SECTION_GAURAV_PROJECTS if grouped.get(p)]
    other_keys = sorted(k for k in grouped if k not in ab_set and k not in g_set and grouped.get(k))

    if ab_keys:
        lines.append("## AE & PLAT — @Abhishes")
        lines.append("")
        for project in ab_keys:
            _append_project_tickets(lines, project, grouped[project], id_to_summary)

    if g_keys:
        lines.append("## CLOUD & DPP — @Gaurav")
        lines.append("")
        for project in g_keys:
            _append_project_tickets(lines, project, grouped[project], id_to_summary)

    if other_keys:
        lines.append("## Other projects")
        lines.append("")
        for project in other_keys:
            _append_project_tickets(lines, project, grouped[project], id_to_summary)

    lines.append("---")
    lines.append("Generated by release automation from release-utils output.")
    return "\n".join(lines)


def resolve_assignee_id(api_key: str, assignee_query: str) -> str:
    query = """
    query {
      users(first: 250) {
        nodes { id name displayName email }
      }
    }
    """
    users = linear_request(api_key, query).get("users", {}).get("nodes", [])
    q = assignee_query.lower().strip()
    best = None
    for u in users:
        hay = " ".join(str(u.get(k, "")) for k in ("name", "displayName", "email")).lower()
        if q in hay:
            best = u
            if u.get("name", "").lower() == q or u.get("displayName", "").lower() == q:
                break
    if not best:
        raise RuntimeError(f"Could not find assignee matching '{assignee_query}'")
    return best["id"]


def resolve_template_id(api_key: str, template_name: str) -> str:
    """Resolve template id using root Query.templates (a list, not a connection)."""
    needle = template_name.lower().strip()

    # Linear GraphQL: Query.templates is [Template!]! with no pagination args.
    # (Organization.templates / Team.templates use TemplateConnection with nodes.)
    query_templates = """
    query {
      templates {
        id
        name
        type
        __typename
      }
    }
    """

    data = linear_request(api_key, query_templates)
    raw = data.get("templates", [])
    nodes = raw if isinstance(raw, list) else []
    if not nodes:
        raise RuntimeError("No templates returned by Linear `templates` query")

    # Prefer issue templates (Linear `Template.type` describes entity kind, e.g. issue).
    issue_like = [n for n in nodes if "issue" in str(n.get("type", "")).lower()]
    pool = issue_like or nodes

    for t in pool:
        if str(t.get("name", "")).lower().strip() == needle:
            return t["id"]
    for t in pool:
        if needle in str(t.get("name", "")).lower():
            return t["id"]

    available = ", ".join(sorted(str(t.get("name", "")) for t in pool if t.get("name")))
    raise RuntimeError(f"Template '{template_name}' not found in templates. Available: {available or 'none'}")


def resolve_team_id(api_key: str, team_key: str) -> str:
    """Resolve Linear team id by team key (issue prefix), e.g. HZ -> team for HZ-123 issues."""
    key = team_key.strip()
    if not key:
        raise RuntimeError("team_key is empty")
    query = """
    query TeamByKey($filter: TeamFilter) {
      teams(first: 10, filter: $filter) {
        nodes { id key name }
      }
    }
    """
    variables: Dict[str, Any] = {"filter": {"key": {"eqIgnoreCase": key}}}
    data = linear_request(api_key, query, variables)
    nodes = data.get("teams", {}).get("nodes", [])
    for t in nodes:
        if str(t.get("key", "")).upper() == key.upper():
            return t["id"]
    if nodes:
        return nodes[0]["id"]
    raise RuntimeError(f"No Linear team found for key '{team_key}'")


def create_issue(
    api_key: str,
    title: str,
    summary: str,
    assignee_id: str,
    template_id: str,
    team_id: str,
) -> Dict[str, Any]:
    mutation = """
    mutation IssueCreate($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue { id identifier title url }
      }
    }
    """

    # teamId places the issue on the target team (e.g. HZ). Template fields may still apply.
    base = {
        "title": title,
        "description": summary,
        "assigneeId": assignee_id,
        "teamId": team_id,
    }
    candidate_inputs = [
        {**base, "templateId": template_id},
        {**base, "issueTemplateId": template_id},
    ]

    last_error = None
    for inp in candidate_inputs:
        try:
            created = linear_request(api_key, mutation, {"input": inp}).get("issueCreate", {})
            if not created.get("success"):
                raise RuntimeError("issueCreate returned success=false")
            issue = created.get("issue")
            if not issue:
                raise RuntimeError("issueCreate returned no issue")
            return issue
        except Exception as e:
            last_error = e

    raise RuntimeError(f"Failed creating issue with template fields templateId/issueTemplateId: {last_error}")


def run_create_monthly_release(cfg: MonthlyTicketConfig) -> int:
    """Create the Linear monthly release issue from structured config. Used by CLI and release pipeline."""
    input_path = cfg.input_path
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1

    month_label = cfg.month_label.strip() or datetime.now().strftime("%B %Y")
    grouped, id_to_summary, in_progress_projects = load_release_data(input_path)
    summary = build_summary(grouped, month_label, id_to_summary, in_progress_projects)
    title = cfg.title.strip() or f"Monthly Release - {month_label}"

    api_key = cfg.api_key if cfg.api_key is not None else os.getenv("LINEAR_API_KEY")

    print("Preparing Linear Monthly Release ticket")
    print("=" * 60)
    print(f"Input:          {input_path}")
    print(f"Template name:  {cfg.template_name}")
    print(f"Assignee query: {cfg.assignee_query}")
    print(f"Team:           {cfg.team_id.strip() or f'key={cfg.team_key!r}'}")
    print(f"Title:          {title}")
    print()

    if cfg.dry_run:
        print("[DRY RUN] Summary that will be sent:")
        print()
        print(summary)
        return 0

    if not api_key:
        print("Error: LINEAR_API_KEY not set. Pass --api-key or export LINEAR_API_KEY.", file=sys.stderr)
        return 1

    try:
        assignee_id = resolve_assignee_id(api_key, cfg.assignee_query)
        template_id = cfg.template_id.strip() or resolve_template_id(api_key, cfg.template_name)
        team_id = cfg.team_id.strip() or resolve_team_id(api_key, cfg.team_key)
        print(f"Resolved assignee id: {assignee_id}")
        print(f"Resolved template id: {template_id}")
        print(f"Resolved team id:     {team_id}")
        print()
        print("=" * 60)
        print("Ticket content")
        print("=" * 60)
        print(f"Title:\n{title}")
        print()
        print(f"Assignee ID: {assignee_id}")
        print(f"Template ID: {template_id}")
        print(f"Team ID:     {team_id}")
        print()
        print("Description (issue body):")
        print("-" * 60)
        print(summary)
        print("-" * 60)
        print()

        issue = create_issue(api_key, title, summary, assignee_id, template_id, team_id)
        print()
        print("✅ Monthly Release ticket created")
        print(f"Identifier: {issue.get('identifier')}")
        print(f"Title:      {issue.get('title')}")
        print(f"URL:        {issue.get('url')}")
        return 0
    except Exception as e:
        print(f"❌ Failed to create ticket: {e}", file=sys.stderr)
        return 1


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create Monthly Release ticket in Linear")
    parser.add_argument("--input", "-i", default="generated_files/final_tag_differences.json")
    parser.add_argument("--api-key", default=os.getenv("LINEAR_API_KEY"))
    parser.add_argument("--template-name", default="Monthly Release")
    parser.add_argument("--template-id", default="")
    parser.add_argument("--assignee-query", default="gaurav")
    parser.add_argument(
        "--team-key",
        default="HZ",
        help="Linear team key (issue prefix, e.g. HZ for issues HZ-123). Ignored if --team-id is set.",
    )
    parser.add_argument(
        "--team-id",
        default="",
        help="Linear team UUID. Overrides --team-key when set.",
    )
    parser.add_argument("--title", default="")
    parser.add_argument("--month-label", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    cfg = MonthlyTicketConfig(
        input_path=Path(args.input),
        api_key=args.api_key,
        template_name=args.template_name,
        template_id=args.template_id,
        assignee_query=args.assignee_query,
        team_key=args.team_key,
        team_id=args.team_id,
        title=args.title,
        month_label=args.month_label,
        dry_run=args.dry_run,
    )
    return run_create_monthly_release(cfg)


if __name__ == "__main__":
    sys.exit(main())
