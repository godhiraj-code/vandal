"""Redact host locations in retained evidence without changing measured outcomes."""
import json
import re


def host_paths(value):
    if isinstance(value, dict):
        return {key: host_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [host_paths(item) for item in value]
    if not isinstance(value, str):
        return value
    # Handle native Windows, JSON-escaped text, and Docker Desktop's Linux view.
    value = re.sub(r"(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s]+[\\/]+AppData[\\/]+Local[\\/]+Temp", "<HOST_TEMP>", value)
    value = re.sub(r"(?i)/run/desktop/mnt/host/[a-z]/Users/[^/]+/AppData/Local/Temp", "<HOST_TEMP>", value)
    value = re.sub(r"(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s]+", "<HOST_HOME>", value)
    value = re.sub(r"/(?:home|Users)/[^/\s,\"']+", "<HOST_HOME>", value)
    return re.sub(r"/tmp/vandal-study-[^/\s,\"']+", "<HOST_RUN>", value)


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
        if updated == source:
            return False
    path.write_bytes(updated.encode("utf-8"))
    return True
