"""Bounded static record validation. Never imports suites or launches a process."""
import argparse
import csv
import hashlib
import json
import math
import re
import stat
from datetime import datetime
from pathlib import Path, PurePosixPath
from string import Template
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
MAX_FILE_BYTES = 1024 * 1024
MAX_BUNDLE_BYTES = 10 * MAX_FILE_BYTES


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def _json(data):
    try:
        return json.loads(data.decode('utf-8-sig'), object_pairs_hook=_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError('non-finite JSON number')))
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('invalid JSON encoding or nesting') from exc


def _schema(value, spec, where='record'):
    """Validate the exact JSON Schema subset used in run.schema.json, stdlib-only."""
    types = spec.get('type', [])
    types = [types] if isinstance(types, str) else types
    kinds = {'object': type(value) is dict, 'array': type(value) is list,
             'string': type(value) is str, 'integer': type(value) is int,
             'number': type(value) in (int, float), 'boolean': type(value) is bool,
             'null': value is None}
    if types and not any(kinds[t] for t in types):
        raise ValueError(where + ': incorrect type')
    if 'enum' in spec and value not in spec['enum']:
        raise ValueError(where + ': unsupported value')
    if isinstance(value, dict):
        if set(spec.get('required', [])) - value.keys():
            raise ValueError(where + ': missing fields')
        props = spec.get('properties', {})
        if spec.get('additionalProperties') is False and value.keys() - props.keys():
            raise ValueError(where + ': unknown fields')
        for key in value:
            _schema(value[key], props.get(key, {}), where + '.' + key)
    elif isinstance(value, list):
        if not spec.get('minItems', 0) <= len(value) <= spec.get('maxItems', len(value)):
            raise ValueError(where + ': invalid array length')
        for item in value:
            _schema(item, spec.get('items', {}), where + '[]')
    elif isinstance(value, str):
        if not spec.get('minLength', 0) <= len(value) <= spec.get('maxLength', len(value)):
            raise ValueError(where + ': invalid string length')
        if 'pattern' in spec and not re.fullmatch(spec['pattern'], value):
            raise ValueError(where + ': invalid format')
    elif type(value) in (int, float):
        if (type(value) is float and not math.isfinite(value)) or value < spec.get('minimum', value) or value > spec.get('maximum', value):
            raise ValueError(where + ': invalid numeric range')


def _safe_name(name):
    if (not isinstance(name, str) or not name or len(name) > 240
            or any(ord(c) < 32 for c in name) or '\\' in name or ':' in name
            or name.startswith(('/', '~')) or any(p in ('', '.', '..') for p in name.split('/'))):
        raise ValueError('unsafe bundle path')
    for part in PurePosixPath(name).parts:
        if part.endswith((' ', '.')) or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?', part):
            raise ValueError('unsafe platform path')
    return name


def _regular_bytes(root, name, limit=MAX_FILE_BYTES):
    name = _safe_name(name)
    path = root
    for part in (None, *PurePosixPath(name).parts):
        if part is not None:
            path = path / part
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
            raise ValueError('symlink/reparse point in bundle path')
    if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1 or info.st_size > limit:
        raise ValueError('bundle entry must be a bounded regular file without hardlinks')
    if root.resolve() not in path.resolve().parents:
        raise ValueError('bundle path escapes root')
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('bundle file exceeds size bound')
    return data


def render_prompt(packet, template=None):
    template = (HERE / 'prompt.md').read_bytes() if template is None else template
    parsed = urlsplit(packet['app_url'])
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('app URL must be credential-free loopback HTTP with explicit port')
    return Template(template.decode('utf-8')).substitute(packet).encode('utf-8')


def suite_digest(files):
    return sha256(json.dumps(sorted(files, key=lambda f: f['path']), sort_keys=True,
                             separators=(',', ':')).encode('utf-8'))


def load_run(bundle, *, apps_manifest=None, protocol=None, template=None):
    """Read a frozen bundle; baseline validity is evidence consistency, not proof.

    Inputs must be immutable while reading. This validator provides no execution
    authorization and cannot attest that self-reported logs are truthful.
    """
    root = Path(bundle).absolute()
    try:
        record = _json(_regular_bytes(root, 'run.json', 512 * 1024))
        _schema(record, json.loads((HERE / 'run.schema.json').read_text()))
        protocol_bytes = (protocol or HERE / 'PROTOCOL.md').read_bytes()
        template_bytes = (template or HERE / 'prompt.md').read_bytes()
        if record['protocol_sha256'] != sha256(protocol_bytes) or record['prompt_template_sha256'] != sha256(template_bytes):
            raise ValueError('protocol/template hash mismatch')
        prompt = _regular_bytes(root, 'prompt.txt')
        if prompt != render_prompt(record['task_packet'], template_bytes) or sha256(prompt) != record['prompt_sha256']:
            raise ValueError('rendered prompt mismatch')
        with (apps_manifest or HERE / 'apps.proposed.csv').open(encoding='utf-8', newline='') as stream:
            apps = list(csv.DictReader(stream))
        matches = [a for a in apps if a['repo'] == record['app']['repo'] and a['commit_sha'] == record['app']['commit_sha']]
        if len(matches) != 1:
            raise ValueError('app snapshot is not uniquely listed in the selected manifest')
        start = datetime.strptime(record['started_at'], '%Y-%m-%dT%H:%M:%SZ')
        end = datetime.strptime(record['ended_at'], '%Y-%m-%dT%H:%M:%SZ')
        if end < start:
            raise ValueError('end time precedes start time')
        agent = record['agent']
        if agent['version_pin'] == 'immutable' and (agent['artifact_sha256'] is None
                or agent['version'].lower() in {'latest', 'unknown', 'default'}
                or agent['model_snapshot'].lower() in {'latest', 'unknown', 'default'}):
            raise ValueError('immutable agent/model pin is incomplete')
        refs = [agent['config'], *record['suite_files'], *[b['log'] for b in record['baseline_runs']]]
        names, total = set(), len(prompt)
        for ref in refs:
            key = ref['path'].casefold()
            if key in names or key in {'run.json', 'prompt.txt'}:
                raise ValueError('duplicate or reserved file path')
            names.add(key)
            data = _regular_bytes(root, ref['path'])
            total += len(data)
            if total > MAX_BUNDLE_BYTES or sha256(data) != ref['sha256']:
                raise ValueError('file hash mismatch or bundle size bound exceeded')
        selected = set()
        for file in record['suite_files']:
            path = _safe_name(file['path'])
            if not path.startswith('suite/') or not path.endswith('.py'):
                raise ValueError('suite files must be Python files under suite/')
            selected.add(path)
        suite_root = root / 'suite'
        actual = set()
        try:
            info = suite_root.lstat()
        except FileNotFoundError:
            info = None
        if info is not None:
            if not stat.S_ISDIR(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
                raise ValueError('suite root must be a directory without symlinks/reparse points')
            for index, path in enumerate(suite_root.rglob('*')):
                if index >= 1000:
                    raise ValueError('suite tree exceeds entry bound')
                if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
                    raise ValueError('symlink/reparse point in suite tree')
                if not path.is_dir():
                    actual.add(path.relative_to(root).as_posix())
        if actual != selected:
            raise ValueError('unlisted or missing suite files')
        digest = suite_digest(record['suite_files'])
        reasons = []
        if record['generation']['status'] == 'completed' and record['generation']['turns'] == 0:
            reasons.append('completed generation recorded no assistant turns')
        if record['generation']['status'] != 'completed':
            if not record['generation']['failure_reason'].strip():
                raise ValueError('failed generation needs a reason')
            reasons.append('generation did not complete')
        if (end-start).total_seconds() > record['generation']['budget_seconds']:
            reasons.append('generation time budget exceeded')
        if not selected:
            reasons.append('no suite')
        baselines = record['baseline_runs']
        if len(baselines) != 3:
            reasons.append('three consecutive baselines required')
        identities = None
        for baseline in baselines:
            nodes = baseline['nodeids']
            if len(set(nodes)) != len(nodes) or len(nodes) != baseline['collected']:
                raise ValueError('invalid collected test identities')
            if baseline['suite_sha256'] != digest:
                raise ValueError('baseline refers to different suite bytes')
            if identities is not None and identities != sorted(nodes):
                reasons.append('baseline collection changed')
            identities = sorted(nodes)
            if (not baseline['offline'] or baseline['exit_code'] != 0 or baseline['collected'] < 1
                    or baseline['passed'] != baseline['collected']
                    or any(baseline[k] for k in ('failed', 'errors', 'skipped', 'xfailed', 'xpassed'))):
                reasons.append('baseline did not fully pass offline')
        return {'record': record, 'suite_sha256': digest, 'baseline_valid': not reasons,
                'reasons': sorted(set(reasons)), 'execution_authorized': False,
                'version_limitation': agent['version_pin'] == 'recorded_hosted'}
    except (OSError, KeyError, TypeError, RecursionError) as exc:
        raise ValueError('invalid or unreadable run bundle: ' + str(exc)) from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    try:
        result = load_run(args.bundle)
    except ValueError as exc:
        parser.exit(2, str(exc) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'record'}, sort_keys=True))


if __name__ == '__main__':
    main()
