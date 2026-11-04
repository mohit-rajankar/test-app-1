#!/usr/bin/env python3
"""
Developer Username & Branch Name Helper for Infineo Repositories
================================================================
Discovers the real developer username from Git/GitHub configurations
and formats compliant branch names according to Infineo engineering policy:

  <type>/<developer>/<YYYY-MM-DD>/<description>

Usage:
  1. Print detected developer username:
       python .githooks/get_developer_username.py

  2. Generate compliant branch name:
       python .githooks/get_developer_username.py feature add-login-form
       python .githooks/get_developer_username.py bugfix fix-auth-timeout

  3. Automatically create and checkout the branch:
       python .githooks/get_developer_username.py --create feature add-login-form

  4. Output JSON details:
       python .githooks/get_developer_username.py --json feature add-login-form
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ALLOWED_BRANCH_TYPES = (
    "feature", "bugfix", "hotfix", "chore", "docs", "refactor", "test"
)
DISALLOWED_PLACEHOLDERS = {
    "dev", "developer", "agent", "xyz", "temp", "test", "placeholder",
    "user", "none", "unknown", "git-central-hooks[bot]", "bot"
}


def sanitize_identifier(raw_identifier: str) -> str:
    """Sanitizes an identifier to alphanumeric characters, hyphens, and underscores."""
    if not raw_identifier:
        return ""
    normalized_identifier = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_identifier.strip().lower())
    clean_identifier = re.sub(r"-+", "-", normalized_identifier).strip("-")
    return clean_identifier


def run_git_command(command_arguments: list) -> str:
    """Executes a git command and returns stripped stdout, or empty string on error."""
    try:
        command_output = subprocess.check_output(
            command_arguments,
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.DEVNULL
        )
        return command_output.strip()
    except Exception:
        return ""


def detect_developer_username(target_repo_path: Optional[Path] = None) -> str:
    """
    Detects the authentic developer username using multiple discovery strategies:
      1. Git config github.user
      2. GitHub CLI (gh api user -q .login)
      3. Remote origin repository owner (https://github.com/owner/repo or git@github.com:owner/repo)
      4. Git config user.name (slugified)
      5. Git config user.email (noreply or prefix before @)
      6. Environment variables (GITHUB_USER, USER, USERNAME)
    """
    git_base_args = ["git"]
    if target_repo_path:
        git_base_args.extend(["-C", str(target_repo_path)])

    candidate_sources = []

    # Strategy 1: Git config github.user
    github_user_config = run_git_command(git_base_args + ["config", "--get", "github.user"])
    if github_user_config:
        candidate_sources.append(("git config github.user", github_user_config))

    # Strategy 2: GitHub CLI authentication status
    try:
        gh_login = subprocess.check_output(
            ["gh", "api", "user", "-q", ".login"],
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.DEVNULL
        ).strip()
        if gh_login:
            candidate_sources.append(("gh cli user", gh_login))
    except Exception:
        pass

    # Strategy 3: Remote origin owner (e.g. https://github.com/mohit-rajankar/repo.git)
    remote_origin_url = run_git_command(git_base_args + ["config", "--get", "remote.origin.url"])
    if remote_origin_url:
        origin_match = re.search(r"github\.com[:/](?P<owner>[^/]+)/", remote_origin_url)
        if origin_match:
            candidate_sources.append(("remote.origin.url owner", origin_match.group("owner")))

    # Strategy 4: Git config user.name
    git_user_name = run_git_command(git_base_args + ["config", "--get", "user.name"])
    if git_user_name:
        candidate_sources.append(("git config user.name", git_user_name))

    # Strategy 5: Git config user.email
    git_user_email = run_git_command(git_base_args + ["config", "--get", "user.email"])
    if git_user_email:
        # Check GitHub noreply pattern: 12345+username@users.noreply.github.com
        noreply_match = re.search(r"(?:\d+\+)?([a-zA-Z0-9_-]+)@users\.noreply\.github\.com", git_user_email)
        if noreply_match:
            candidate_sources.append(("github noreply email", noreply_match.group(1)))
        elif "@" in git_user_email:
            email_prefix = git_user_email.split("@")[0]
            candidate_sources.append(("git email prefix", email_prefix))

    # Strategy 6: Environment variables
    for environment_key in ("GITHUB_USER", "GIT_AUTHOR_NAME", "USERNAME", "USER"):
        environment_value = os.getenv(environment_key)
        if environment_value:
            candidate_sources.append((f"env ${environment_key}", environment_value))

    # Evaluate candidates in priority order, rejecting placeholders
    for strategy_name, raw_candidate in candidate_sources:
        sanitized_name = sanitize_identifier(raw_candidate)
        if not sanitized_name:
            continue
        if sanitized_name.lower() in DISALLOWED_PLACEHOLDERS:
            continue
        return sanitized_name

    return "developer"


def build_branch_name(
    branch_type: str,
    description_text: str,
    developer_username: Optional[str] = None,
    branch_date: Optional[datetime.date] = None
) -> str:
    """Constructs a policy-compliant branch name."""
    clean_type = branch_type.strip().lower()
    if clean_type not in ALLOWED_BRANCH_TYPES:
        clean_type = "feature"

    clean_developer = developer_username or detect_developer_username()
    effective_date = branch_date or datetime.date.today()
    formatted_date = effective_date.strftime("%Y-%m-%d")

    clean_description = sanitize_identifier(description_text)
    if not clean_description:
        clean_description = "task"

    return f"{clean_type}/{clean_developer}/{formatted_date}/{clean_description}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect real developer username and construct policy-compliant Infineo branch names."
    )
    parser.add_argument(
        "type",
        nargs="?",
        default=None,
        help=f"Branch type ({', '.join(ALLOWED_BRANCH_TYPES)})"
    )
    parser.add_argument(
        "description",
        nargs="?",
        default=None,
        help="Brief description of the branch task (e.g. 'add-login-page')"
    )
    parser.add_argument(
        "--create", "-c",
        action="store_true",
        help="Directly create and checkout the constructed branch"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON details"
    )
    parser.add_argument(
        "--repo-path",
        type=Path,
        default=None,
        help="Target repository directory (default: current directory)"
    )

    parsed_arguments = parser.parse_args()

    detected_username = detect_developer_username(target_repo_path=parsed_arguments.repo_path)
    today_string = datetime.date.today().strftime("%Y-%m-%d")

    if not parsed_arguments.type and not parsed_arguments.description:
        # Bare invocation: print the detected username
        if parsed_arguments.json:
            print(json.dumps({
                "developer_username": detected_username,
                "date": today_string,
                "allowed_types": list(ALLOWED_BRANCH_TYPES)
            }, indent=2))
        else:
            print(detected_username)
        return 0

    branch_type = parsed_arguments.type or "feature"
    description_text = parsed_arguments.description or "update"
    formatted_branch = build_branch_name(
        branch_type=branch_type,
        description_text=description_text,
        developer_username=detected_username
    )

    if parsed_arguments.create:
        creation_result = subprocess.run(["git", "checkout", "-b", formatted_branch])
        if creation_result.returncode != 0:
            sys.stderr.write(f"Failed to create branch '{formatted_branch}'.\n")
            return creation_result.returncode
        print(f"Switched to a new branch '{formatted_branch}'")
        return 0

    if parsed_arguments.json:
        print(json.dumps({
            "developer_username": detected_username,
            "branch_type": branch_type,
            "date": today_string,
            "description": sanitize_identifier(description_text),
            "branch_name": formatted_branch
        }, indent=2))
    else:
        print(formatted_branch)

    return 0


if __name__ == "__main__":
    sys.exit(main())
