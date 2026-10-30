#!/usr/bin/env python3
"""Validate saved evidence structure, never certify real operation or visual review."""
import json, os
from pathlib import Path

def validate(root):
    root = Path(root).resolve()
    cfg = json.loads((root / 'project.json').read_text())
    if cfg.get('mode') != 'self-operated':
        return []
    errors = []
    try:
        ev = json.loads((root / 'evidence.json').read_text())
    except (OSError, ValueError) as e:
        return ['Missing/invalid evidence.json: ' + str(e)]
    steps = ev.get('steps', [])
    if not isinstance(steps, list) or any(not isinstance(s, dict) for s in steps):
        return ['steps must be a list of objects']
    ids = [s.get('id') for s in steps]
    if not all(isinstance(i, str) and i for i in ids) or len(set(ids)) != len(ids):
        errors.append('Evidence IDs must be nonempty and unique')
    for kind in ['entry', 'input', 'execution', 'result']:
        if not any(s.get('kind') == kind for s in steps):
            errors.append('Missing evidence kind: ' + kind)
    for s in steps:
        for key in ['action', 'observed', 'shot']:
            if not isinstance(s.get(key), str) or not s[key].strip():
                errors.append(str(s.get('id')) + ': missing ' + key)
        shot = (root / s.get('shot', '')).resolve()
        if not shot.is_relative_to(root) or not shot.is_file() or shot.stat().st_size == 0:
            errors.append(str(s.get('id')) + ': screenshot missing/outside project')
        if s.get('checked') is not True:
            errors.append(str(s.get('id')) + ': review not recorded')
    for key in ['result_verified', 'privacy_reviewed']:
        if ev.get(key) is not True:
            errors.append(key + ' not recorded')
    for sc in cfg.get('scenes', []):
        refs = sc.get('evidence_ids', [])
        if sc.get('shot') and not refs:
            errors.append(str(sc.get('id')) + ': shot scene lacks evidence_ids')
        if not isinstance(refs, list) or any(i not in ids for i in refs):
            errors.append(str(sc.get('id')) + ': invalid evidence_ids')
    return errors

if __name__ == '__main__':
    errors = validate(os.environ.get('TV_PROJECT', '.'))
    if errors:
        raise SystemExit('Evidence check failed:\n- ' + '\n- '.join(errors))
    print('Evidence structure passed (or supplied-material mode); actual visual review still required.')
