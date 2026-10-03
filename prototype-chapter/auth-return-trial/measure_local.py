#!/usr/bin/env python3
"""Private loopback GoTrue experiment; never print mail links or credentials.

The Node adapter is an in-memory REST seam, not supabase-js or a native app.
Synthetic users stay in the dedicated disposable sns-trio-local stack.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--cli', required=True)
    parser.add_argument('--node', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError('retain prior evidence: choose a fresh output path')
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    status = subprocess.run(
        [args.cli, 'status', '--workdir', '/tmp/sns-trio-local', '-o', 'json'],
        capture_output=True, text=True, check=True,
    )
    settings = json.loads(status.stdout)
    base = settings['API_URL']
    if base != 'http://127.0.0.1:54321':
        raise RuntimeError('only the dedicated loopback stack is permitted')
    key = settings['ANON_KEY']
    names = subprocess.check_output(
        ['docker', 'ps', '--format', '{{.Names}}'], text=True,
    ).splitlines()
    names = [n for n in names if n.startswith('supabase_') and n.endswith('_sns-trio-local')]
    required = {f'supabase_{n}_sns-trio-local' for n in ('db', 'kong', 'inbucket', 'auth')}
    if not required.issubset(names):
        raise RuntimeError('required dedicated services are not running')
    for name in names:
        bindings = json.loads(subprocess.check_output(
            ['docker', 'inspect', '--format', '{{json .HostConfig.PortBindings}}', name],
            text=True,
        )) or {}
        if name in required - {'supabase_auth_sns-trio-local'} and not bindings:
            raise RuntimeError('required loopback ports are absent')
        if not all(values and all(v.get('HostIp') == '127.0.0.1' for v in values)
                   for values in bindings.values()):
            raise RuntimeError('a dedicated service exposes a non-loopback port')

    def api(path, data):
        request = urllib.request.Request(
            base + path, data=json.dumps(data).encode(),
            headers={'apikey': key, 'Content-Type': 'application/json'}, method='POST',
        )
        try:
            response = urllib.request.urlopen(request, timeout=15)
        except urllib.error.HTTPError as exc:
            response = exc
        payload = response.read()
        return response.status, json.loads(payload) if payload else None

    def find_mail_link(email, kind):
        for _ in range(40):
            with urllib.request.urlopen('http://127.0.0.1:54324/api/v1/messages', timeout=5) as response:
                mail = json.load(response)
            for message in mail['messages']:
                if not any(x.get('Address') == email for x in message.get('To', [])):
                    continue
                with urllib.request.urlopen(
                    'http://127.0.0.1:54324/api/v1/message/' + message['ID'], timeout=5,
                ) as response:
                    detail = json.load(response)
                for raw in re.findall(r'href="([^"]+)"', detail.get('HTML', '')):
                    link = raw.replace('&amp;', '&')
                    parsed = urllib.parse.urlsplit(link)
                    if (parsed.scheme == 'http' and parsed.netloc == '127.0.0.1:54321'
                            and parsed.path == '/auth/v1/verify'
                            and urllib.parse.parse_qs(parsed.query).get('type') == [kind]):
                        return link
            time.sleep(.1)
        raise RuntimeError('local trial message not found')

    def verify_redirect(link):
        opener = urllib.request.build_opener(NoRedirect)
        try:
            response = opener.open(link, timeout=15)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            location = response.headers.get('Location', '')
            response.read()
            if response.status not in (302, 303) or not location:
                raise RuntimeError('local verification did not redirect')
        parsed = urllib.parse.urlsplit(location)
        if parsed.scheme != 'http' or parsed.netloc != '127.0.0.1:3000' or parsed.path not in ('', '/'):
            raise RuntimeError('local callback target escaped the trial')
        return location

    email = 'return-' + uuid.uuid4().hex + '@example.invalid'
    code, signup = api('/auth/v1/signup', {'email': email, 'password': secrets.token_urlsafe(24)})
    if code != 200 or not isinstance(signup, dict) or signup.get('access_token'):
        raise RuntimeError('confirmation-enabled signup precondition failed')
    signup_link = find_mail_link(email, 'signup')
    confirmed = verify_redirect(signup_link)
    reused = verify_redirect(signup_link)
    code, _ = api('/auth/v1/recover', {'email': email})
    if code != 200:
        raise RuntimeError('local recovery request failed')
    recovery = verify_redirect(find_mail_link(email, 'recovery'))
    bridge = Path(__file__).with_name('local_adapter.mjs')
    outcome = subprocess.run(
        [args.node, str(bridge)],
        input=json.dumps({'base': base, 'key': key, 'confirmed': confirmed,
                          'reused': reused, 'recovery': recovery}),
        capture_output=True, text=True, timeout=45,
    )
    # Child diagnostics must never be echoed: its stdin contains bearer tokens.
    if outcome.returncode != 0 or outcome.stderr:
        raise RuntimeError('local adapter failed; private diagnostics retained in memory only')
    measured = json.loads(outcome.stdout)
    if set(measured) != {'scope', 'checks'} or measured['scope'] != 'REST_ADAPTER_NOT_SDK_OR_APP':
        raise RuntimeError('unexpected adapter evidence shape')
    report = {
        'scope': 'LOCAL_GOTRUE_AUTH_RETURN_COMPONENT_NON_FORMAL',
        'started_at_utc': started_at,
        'completed_at_utc': datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(Path(__file__).parent.glob('*')) if p.is_file()},
        'adapter_scope': measured['scope'], 'checks': measured['checks'],
        'all_measured_checks_pass': all(c['passed'] for c in measured['checks']),
        'not_measured': ['supabase_js_setSession', 'React_Native_URL_polyfill',
                         'external_email_delivery', 'device_deep_link', 'app_session_restore',
                         'password_recovery_purpose_proof', 'B5_B18_formal_decision',
                         'D4_authoring_effort', 'G6_independent_execution'],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as output:
        output.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'checks': len(measured['checks']),
                      'passed': sum(c['passed'] for c in measured['checks']),
                      'scope': report['scope']}))
    raise SystemExit(0 if report['all_measured_checks_pass'] else 2)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # urllib/subprocess exceptions can contain a request URL or child payload.
        # Keep diagnostics small rather than risk exposing a bearer callback.
        print(json.dumps({'scope': 'LOCAL_GOTRUE_AUTH_RETURN_COMPONENT_NON_FORMAL',
                          'failed': True, 'error_class': type(error).__name__}))
        raise SystemExit(2) from None
