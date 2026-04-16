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
    line_stripped = (line or "").strip()
    if not line_stripped:
        return "", ""
    meta_match = _TICKET_WITH_META.match(line_stripped)
    if meta_match:
        return meta_match.group(1).strip(), meta_match.group(3).strip()
    id_only_match = _TICKET_ID_ONLY.match(line_stripped)
    if id_only_match:
        return id_only_match.group(1), ""
    return line_stripped, ""


def ticket_summaries_from_all_tickets(data: Dict[str, Any]) -> Dict[str, str]:
    """Map ticket id -> title/summary from `all_tickets` strings (see process_all_repos)."""
    summaries: Dict[str, str] = {}
    raw_entries = data.get("all_tickets")
    if not isinstance(raw_entries, list):
        return summaries
    for raw_line in raw_entries:
        if not isinstance(raw_line, str):
            continue
        ticket_id, summary_text = parse_ticket_line(raw_line)
        if ticket_id:
            summaries[ticket_id] = summary_text
    return summaries


# Linear API returns project.state; active work is typically "started" (UI: In Progress).
IN_PROGRESS_PROJECT_STATES = frozenset({"started"})


def linear_projects_in_progress(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Subset of `projects` from final_tag_differences.json where state is in progress."""
    raw_projects = data.get("projects")
    if not isinstance(raw_projects, list):
        return []
    in_progress: List[Dict[str, Any]] = []
    for project_entry in raw_projects:
        if not isinstance(project_entry, dict):
            continue
        state_normalized = str(project_entry.get("state", "")).strip().lower()
        if state_normalized in IN_PROGRESS_PROJECT_STATES:
            in_progress.append(project_entry)
    return sorted(
        in_progress,
        key=lambda row: str(row.get("name", "") or "").lower(),
    )


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

    ticket_summaries = ticket_summaries_from_all_tickets(data)
    projects_in_progress_list = linear_projects_in_progress(data)

    grouped = data.get("tickets_by_project")
    if isinstance(grouped, dict) and grouped:
        by_prefix: Dict[str, List[str]] = {}
        for prefix, ticket_list in grouped.items():
            if isinstance(ticket_list, list):
                by_prefix[prefix] = sorted(set(str(x) for x in ticket_list if x))
        return (
            dict(sorted(by_prefix.items(), key=lambda kv: kv[0])),
            ticket_summaries,
            projects_in_progress_list,
        )

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
    return (
        dict(sorted(derived.items(), key=lambda kv: kv[0])),
        ticket_summaries,
        projects_in_progress_list,
    )


# Project prefixes grouped for Linear mentions in the monthly summary body
SECTION_ABHISHES_PROJECTS = ("AE", "PLAT")
SECTION_GAURAV_PROJECTS = ("CLOUD", "DPP")


def _append_project_tickets(
    lines: List[str],
    project_prefix: str,
    tickets: List[str],
    ticket_id_to_summary: Dict[str, str],
) -> None:
    if not tickets:
        return
    lines.append(f"### {project_prefix} ({len(tickets)})")
    for ticket_id in tickets:
        summary_text = ticket_id_to_summary.get(ticket_id, "").strip()
        if summary_text:
            lines.append(f"- `{ticket_id}` — {summary_text}")
        else:
            lines.append(f"- `{ticket_id}`")
    lines.append("")


def _append_linear_projects_in_progress(
    lines: List[str],
    linear_projects: List[Dict[str, Any]],
) -> None:
    if not linear_projects:
        return
    lines.append("## Projects — In Progress")
    lines.append("")
    for project in linear_projects:
        display_name = str(project.get("name") or "Untitled").strip() or "Untitled"
        project_url = str(project.get("url") or "").strip()
        description = str(project.get("description") or "").strip()
        progress_value = project.get("progress")
        percent_label = ""
        if isinstance(progress_value, (int, float)):
            percent_label = f"{progress_value * 100:.0f}%"
        bullet = f"- [{display_name}]({project_url})" if project_url else f"- **{display_name}**"
        if percent_label:
            bullet = f"{bullet} — {percent_label}"
        lines.append(bullet)
        if description:
            lines.append(f"  {description}")
    lines.append("")


def build_summary(
    grouped: Dict[str, List[str]],
    month_label: str,
    ticket_id_to_summary: Optional[Dict[str, str]] = None,
    in_progress_projects: Optional[List[Dict[str, Any]]] = None,
) -> str:
    ticket_id_to_summary = ticket_id_to_summary or {}
    in_progress_projects = in_progress_projects or []
    total = sum(len(ticket_ids) for ticket_ids in grouped.values())
    lines = [
        f"Monthly release summary for {month_label}.",
        "",
        f"Total unique tickets: {total}",
        "",
    ]

    _append_linear_projects_in_progress(lines, in_progress_projects)

    abhishes_prefixes = set(SECTION_ABHISHES_PROJECTS)
    gaurav_prefixes = set(SECTION_GAURAV_PROJECTS)

    abhishes_section_keys = [
        prefix for prefix in SECTION_ABHISHES_PROJECTS if grouped.get(prefix)
    ]
    gaurav_section_keys = [
        prefix for prefix in SECTION_GAURAV_PROJECTS if grouped.get(prefix)
    ]
    other_prefix_keys = sorted(
        prefix
        for prefix in grouped
        if prefix not in abhishes_prefixes
        and prefix not in gaurav_prefixes
        and grouped.get(prefix)
    )

    if abhishes_section_keys:
        lines.append("## AE & PLAT — @Abhishes")
        lines.append("")
        for prefix in abhishes_section_keys:
            _append_project_tickets(
                lines, prefix, grouped[prefix], ticket_id_to_summary
            )

    if gaurav_section_keys:
        lines.append("## CLOUD & DPP — @Gaurav")
        lines.append("")
        for prefix in gaurav_section_keys:
            _append_project_tickets(
                lines, prefix, grouped[prefix], ticket_id_to_summary
            )

    if other_prefix_keys:
        lines.append("## Other projects")
        lines.append("")
        for prefix in other_prefix_keys:
            _append_project_tickets(
                lines, prefix, grouped[prefix], ticket_id_to_summary
            )

    lines.append("---")
    lines.append("Generated by release automation from release-utils output.")
    return "\n".join(lines)


def resolve_assignee_id(api_key: str, assignee_query: str) -> str:
    graphql_query = """
    query {
      users(first: 250) {
        nodes { id name displayName email }
      }
    }
    """
    user_nodes = linear_request(api_key, graphql_query).get("users", {}).get("nodes", [])
    query_normalized = assignee_query.lower().strip()
    selected_user = None
    for user in user_nodes:
        searchable = " ".join(
            str(user.get(key, "")) for key in ("name", "displayName", "email")
        ).lower()
        if query_normalized in searchable:
            selected_user = user
            if (
                user.get("name", "").lower() == query_normalized
                or user.get("displayName", "").lower() == query_normalized
            ):
                break
    if not selected_user:
        raise RuntimeError(f"Could not find assignee matching '{assignee_query}'")
    return selected_user["id"]


def resolve_template_id(api_key: str, template_name: str) -> str:
    """Resolve template id using root Query.templates (a list, not a connection)."""
    template_name_normalized = template_name.lower().strip()

    # Linear GraphQL: Query.templates is [Template!]! with no pagination args.
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

    response_data = linear_request(api_key, query_templates)
    template_rows = response_data.get("templates", [])
    template_list = template_rows if isinstance(template_rows, list) else []
    if not template_list:
        raise RuntimeError("No templates returned by Linear `templates` query")

    issue_templates = [
        row
        for row in template_list
        if "issue" in str(row.get("type", "")).lower()
    ]
    search_pool = issue_templates or template_list

    for template_row in search_pool:
        if str(template_row.get("name", "")).lower().strip() == template_name_normalized:
            return template_row["id"]
    for template_row in search_pool:
        if template_name_normalized in str(template_row.get("name", "")).lower():
            return template_row["id"]

    available_names = ", ".join(
        sorted(str(row.get("name", "")) for row in search_pool if row.get("name"))
    )
    raise RuntimeError(
        f"Template '{template_name}' not found in templates. "
        f"Available: {available_names or 'none'}"
    )


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
    response_data = linear_request(api_key, query, variables)
    team_nodes = response_data.get("teams", {}).get("nodes", [])
    for team in team_nodes:
        if str(team.get("key", "")).upper() == key.upper():
            return team["id"]
    if team_nodes:
        return team_nodes[0]["id"]
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

    last_error: Optional[Exception] = None
    for issue_input in candidate_inputs:
        try:
            payload = linear_request(api_key, mutation, {"input": issue_input}).get(
                "issueCreate", {}
            )
            if not payload.get("success"):
                raise RuntimeError("issueCreate returned success=false")
            created_issue = payload.get("issue")
            if not created_issue:
                raise RuntimeError("issueCreate returned no issue")
            return created_issue
        except Exception as exc:
            last_error = exc

    raise RuntimeError(
        f"Failed creating issue with template fields templateId/issueTemplateId: {last_error}"
    )


def run_create_monthly_release(cfg: MonthlyTicketConfig) -> int:
    """Create the Linear monthly release issue from structured config. Used by CLI and release pipeline."""
    input_path = cfg.input_path
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1

    month_label = cfg.month_label.strip() or datetime.now().strftime("%B %Y")
    grouped, ticket_id_to_summary, in_progress_projects = load_release_data(input_path)
    summary = build_summary(
        grouped, month_label, ticket_id_to_summary, in_progress_projects
    )
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
    except Exception as exc:
        print(f"❌ Failed to create ticket: {exc}", file=sys.stderr)
        return 1


def build_argument_parser() -> argparse.ArgumentParser:
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
    args = build_argument_parser().parse_args()
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
