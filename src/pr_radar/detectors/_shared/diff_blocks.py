def file_diff_block(*, path: str, diff: str) -> str:
    current_block: list[str] = []

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            if _diff_header_matches_path(current_block, path):
                return "\n".join(current_block)
            current_block = [line]
            continue
        if current_block:
            current_block.append(line)

    if _diff_header_matches_path(current_block, path):
        return "\n".join(current_block)
    return ""


def added_lines(diff: str) -> tuple[str, ...]:
    return tuple(
        line[1:].strip()
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )


def _diff_header_matches_path(block: list[str], path: str) -> bool:
    if not block:
        return False
    header_paths = block[0].removeprefix("diff --git ").split()
    return f"a/{path}" in header_paths or f"b/{path}" in header_paths
