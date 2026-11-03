import ast
import os
import re
import sys
import fnmatch
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

EXCLUSION_EXTENSIONS = ('.md', '.txt', '.json', '.ini', '.yaml', '.yml')
DIR_EXCLUSION_PATTERNS = (
    '*alembic/*', '*\\alembic\\*',
    '*tests/*', '*\\tests\\*',
    '*venv/*', '*\\venv\\*',
    '*.git/*', '*\\.git\\*',
    '*__pycache__/*', '*\\__pycache__\\*'
)
SINGLE_LETTER_REGEX = re.compile(r'(?<![%\w])\b[a-zA-Z]\b(?!\w)')


class IdentifierVisitor(ast.NodeVisitor):
    def __init__(self, target_lines=None):
        self.target_lines = target_lines
        self.violations = []

    def _check_name(self, identifier_name: str, lineno: int, col_offset: int, kind: str):
        if self.target_lines is not None and lineno not in self.target_lines:
            return
        if SINGLE_LETTER_REGEX.search(identifier_name):
            self.violations.append((identifier_name, lineno, col_offset, kind))

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Store):
            self._check_name(node.id, node.lineno, node.col_offset, "variable assignment")
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg):
        self._check_name(node.arg, node.lineno, node.col_offset, "parameter")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if node.name:
            self._check_name(node.name, node.lineno, node.col_offset, "exception variable")
        self.generic_visit(node)

    def visit_alias(self, node: ast.alias):
        if node.asname:
            self._check_name(node.asname, node.lineno, node.col_offset, "import alias")
        self.generic_visit(node)


def is_excluded(file_path: str) -> bool:
    normalized_path = file_path.replace("\\", "/")
    if any(normalized_path.endswith(extension) for extension in EXCLUSION_EXTENSIONS):
        return True
    if any(fnmatch.fnmatch(normalized_path, pattern.replace("\\", "/")) for pattern in DIR_EXCLUSION_PATTERNS):
        return True
    if not normalized_path.endswith(".py"):
        return True
    return False


def get_staged_python_files():
    try:
        git_output = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            text=True,
            stderr=subprocess.DEVNULL
        )
        staged_files = [line.strip() for line in git_output.splitlines() if line.strip()]
        return [filepath for filepath in staged_files if not is_excluded(filepath)]
    except Exception:
        return []


def get_added_line_numbers(file_path: str):
    try:
        diff_output = subprocess.check_output(
            ["git", "diff", "--cached", "-U0", file_path],
            text=True,
            stderr=subprocess.DEVNULL
        )
        added_lines = set()
        for diff_line in diff_output.splitlines():
            if diff_line.startswith("@@"):
                header_parts = diff_line.split()
                for header_part in header_parts:
                    if header_part.startswith("+"):
                        range_spec = header_part[1:].split(",")
                        start_line_number = int(range_spec[0])
                        line_count = int(range_spec[1]) if len(range_spec) > 1 else 1
                        for line_offset in range(start_line_number, start_line_number + line_count):
                            added_lines.add(line_offset)
        return added_lines
    except Exception:
        return None


def get_staged_content(file_path: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f":{file_path}"],
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.DEVNULL
        )
    except Exception:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8", errors="replace") as source_file:
                return source_file.read()
        return ""


def check_file(file_path: str, staged_only: bool = True):
    if staged_only:
        file_content = get_staged_content(file_path)
        target_lines = get_added_line_numbers(file_path)
    else:
        if not os.path.exists(file_path):
            return []
        with open(file_path, "r", encoding="utf-8", errors="replace") as local_file:
            file_content = local_file.read()
        target_lines = None

    if not file_content:
        return []

    try:
        syntax_tree = ast.parse(file_content, filename=file_path)
    except SyntaxError:
        return []

    ast_visitor = IdentifierVisitor(target_lines=target_lines)
    ast_visitor.visit(syntax_tree)

    content_lines = file_content.splitlines()
    detailed_violations = []
    for identifier_name, line_number, col_offset, node_kind in ast_visitor.violations:
        source_line_text = content_lines[line_number - 1].strip() if 0 < line_number <= len(content_lines) else ""
        detailed_violations.append({
            "file": file_path,
            "line": line_number,
            "name": identifier_name,
            "kind": node_kind,
            "text": source_line_text
        })
    return detailed_violations


def main():
    staged_mode = "--all" not in sys.argv
    detected_violations = []

    if staged_mode:
        candidate_files = get_staged_python_files()
        for candidate_file in candidate_files:
            file_violations = check_file(candidate_file, staged_only=True)
            detected_violations.extend(file_violations)
    else:
        for current_root, directory_names, filenames in os.walk("."):
            directory_names[:] = [
                dir_name for dir_name in directory_names
                if dir_name not in {"venv", ".git", "__pycache__", "alembic", "tests", ".agents", ".pytest_cache"}
            ]
            for filename in filenames:
                relative_file_path = os.path.relpath(os.path.join(current_root, filename), ".")
                if not is_excluded(relative_file_path):
                    file_violations = check_file(relative_file_path, staged_only=False)
                    detected_violations.extend(file_violations)

    if detected_violations:
        failure_messages = [
            "\n" + "=" * 60,
            "❌ [Gate 3 FAILED] Single-letter identifiers found in code!",
            "   Rule: All single-letter identifiers must follow the readable-identifiers skill.",
            "=" * 60,
        ]
        for violation in detected_violations:
            failure_messages.append(f"  • {violation['file']}:{violation['line']} -> {violation['kind']} '{violation['name']}'")
            if violation['text']:
                failure_messages.append(f"    Code: {violation['text']}")
        failure_messages.append("\nPlease rename these identifiers semantically before committing.\n")
        sys.stderr.write("\n".join(failure_messages) + "\n")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
