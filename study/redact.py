"""Redact host locations in retained evidence without changing measured outcomes."""
import json
import os
import re
from pathlib import Path


def _redact_text(value):
    # Match only the beginning of an absolute path token, never an internal
    # component (including /work/home) or relative tests/home paths.
    boundary = r"(?<![\w./\\:~+-])"
    homes = {os.environ.get("HOME", ""), str(Path.home())}
    homes.update(str(Path(p).resolve()) for p in tuple(homes) if p and Path(p).is_absolute())
    patterns = [r"(?i:[A-Z]:[\\/]+Users[\\/]+[^\\/\r\n,\"'<>:]+)",
                r"/(?:Users|home)/[^/\r\n,\"'<>:]+"]
    patterns = [re.escape(p.rstrip("/\\")) + r"(?=[/\\]|$|[\s\"',])"
                 for p in sorted(homes, key=len, reverse=True) if p and Path(p).is_absolute() and p.rstrip("/\\")] + patterns
    # Protect identities as individual spans, not entire lines containing ::.
    # Quoted/full-string IDs can contain spaces; ordinary log IDs are tokens.
    ids = []
    node = r"[^\r\n\"<>]*\.py::[^\s\"<>]+"
    if re.fullmatch(node, value) and (value.startswith(("/", "tests/")) or re.match(r"[A-Za-z]:", value)) and " = " not in value:
        # A standalone node ID is measurement data, even with spaces.
        ids.append((0, len(value)))
    for found in re.finditer(r"[\"']([^\r\n\"']*\.py::[^\r\n\"']+)[\"']|(?:[A-Za-z]:[\\/]|/)?[^\s\"'<>]+\.py::[^\s\"'<>]+", value):
        ids.append(found.span(1) if found.group(1) is not None else found.span())
    pattern = re.compile(r"(?:(?P<url>file://)(?=/)|" + boundary + ")(?:" + "|".join(patterns) + ")")
    def replace(match):
        if any(start <= match.start() < end for start, end in ids):
            return match.group(0)
        return (match.group("url") or "") + "<HOST_HOME>"
    return pattern.sub(replace, value)



def host_paths(value):
    if isinstance(value, dict):
        return {key: item if key in {"nodeid", "nodeids"} else host_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [host_paths(item) for item in value]
    if not isinstance(value, str):
        return value
    return _redact_text(value)


def redact_file(path):
    """Returns whether a UTF-8 artifact changed; binary artifacts are untouched."""
    original = path.read_bytes()
    try:
        source = original.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    if path.suffix == ".json":
        try:
            parsed = json.loads(source)
            redacted = host_paths(parsed)
        except (ValueError, RecursionError):
            # Preserve malformed output for the summarizer to reject; redaction
            # must never prevent the runner from recording its terminal status.
            updated = host_paths(source)
            if updated == source:
                return False
            path.write_bytes(updated.encode("utf-8"))
            return True
        if redacted == parsed:
            return False
        updated = json.dumps(redacted, indent=2, ensure_ascii=False) + "\n"
    else:
        updated = host_paths(source)
        if path.name == "baseline.xml":
            updated = re.sub(r'\bhostname=("[^"]*"|\x27[^\x27]*\x27)', 'hostname="runner"', updated)
        if updated == source:
            return False
    path.write_bytes(updated.encode("utf-8"))
    return True
