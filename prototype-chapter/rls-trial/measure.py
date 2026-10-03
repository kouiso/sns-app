#!/usr/bin/env python3
"""Measure local Auth/PostgREST only; never serialize credentials or mail links.

Requires the dedicated sns-trio-local CLI stack and 001_posts.sql. Synthetic
users remain in that disposable stack. This is not an app/session/device test.
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
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('output must be a fresh path; retain earlier measurement evidence')
    result = subprocess.run([args.cli, 'status', '--workdir', '/tmp/sns-trio-local',
                             '-o', 'json'], capture_output=True, text=True, check=True)
    settings = json.loads(result.stdout)
    base = settings['API_URL']
    if base != 'http://127.0.0.1:54321':
        raise RuntimeError('only the dedicated loopback API is permitted')
    key = settings['ANON_KEY']
    checks: list[dict] = []
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()

    def api(method, path, data=None, jwt=None, returning=False):
        headers = {'apikey': key, 'Content-Type': 'application/json'}
        if jwt:
            headers['Authorization'] = 'Bearer ' + jwt
        if returning:
            headers['Prefer'] = 'return=representation,count=exact'
        request = urllib.request.Request(base + path, method=method, headers=headers,
                                         data=json.dumps(data).encode() if data is not None else None)
        try:
            response = urllib.request.urlopen(request, timeout=15)
        except urllib.error.HTTPError as exc:
            response = exc
        payload = response.read()
        return response.status, json.loads(payload) if payload else None

    def check(name, passed, **facts):
        checks.append({'name': name, 'passed': bool(passed), **facts})

    def sql(query):
        p = subprocess.run(['docker', 'exec', 'supabase_db_sns-trio-local',
                            'psql', '-U', 'postgres', '-d', 'postgres', '-At',
                            '-v', 'ON_ERROR_STOP=1', '-c', query],
                           capture_output=True, text=True, check=True)
        return p.stdout.strip()

    for component in ('db', 'kong', 'inbucket'):
        bindings = json.loads(subprocess.check_output([
            'docker', 'inspect', '--format', '{{json .HostConfig.PortBindings}}',
            'supabase_' + component + '_sns-trio-local'], text=True))
        if not bindings or not all(x.get('HostIp') == '127.0.0.1'
                                   for values in bindings.values() for x in values):
            raise RuntimeError('trial container ports must be bound to loopback')
    check('dedicated_ports_loopback_only', True)

    def mail_link(email, message_kind):
        for _ in range(40):
            mail = json.load(urllib.request.urlopen('http://127.0.0.1:54324/api/v1/messages'))
            matches = [m for m in mail['messages']
                       if any(x.get('Address') == email for x in m.get('To', []))]
            if matches:
                message = json.load(urllib.request.urlopen(
                    'http://127.0.0.1:54324/api/v1/message/' + matches[0]['ID']))
                links = re.findall(r'href="([^"]+)"', message.get('HTML', ''))
                candidates = [x.replace('&amp;', '&') for x in links if '/auth/v1/verify' in x]
                candidates = [x for x in candidates if urllib.parse.parse_qs(
                    urllib.parse.urlsplit(x).query).get('type') == [message_kind]]
                if not candidates:
                    time.sleep(.1)
                    continue
                link = candidates[0]
                parsed = urllib.parse.urlsplit(link)
                if parsed.scheme != 'http' or parsed.netloc != '127.0.0.1:54321':
                    raise RuntimeError('mail verification link escaped the local trial')
                opener = urllib.request.build_opener(NoRedirect)
                try:
                    r = opener.open(link, timeout=15)
                except urllib.error.HTTPError as exc:
                    r = exc
                location = r.headers.get('Location', '')
                fragment = urllib.parse.parse_qs(urllib.parse.urlsplit(location).fragment)
                return r.status in (302, 303) and 'error' not in fragment, fragment
            time.sleep(.1)
        return False, {}

    users = []
    run_id = secrets.token_hex(5)
    for label in ('a', 'b', 'unconfirmed'):
        email = f'trial-{run_id}-{label}@example.test'
        password = secrets.token_urlsafe(24)
        status, registered = api('POST', '/auth/v1/signup', {'email': email, 'password': password})
        check('signup_' + label, status == 200 and bool(registered.get('id')) and
              not registered.get('access_token'),
              http=status, immediate_session=bool(registered.get('access_token')))
        status, login = api('POST', '/auth/v1/token?grant_type=password',
                            {'email': email, 'password': password})
        check('unconfirmed_login_denied_' + label, status == 400 and
              login.get('error_code') == 'email_not_confirmed', http=status,
              error_code=login.get('error_code'))
        if label != 'unconfirmed':
            confirmed, _ = mail_link(email, 'signup')
            check('local_confirmation_' + label, confirmed)
            status, login = api('POST', '/auth/v1/token?grant_type=password',
                                {'email': email, 'password': password})
            check('confirmed_login_' + label, status == 200 and bool(login.get('access_token')),
                  http=status)
            users.append({**login, '_trial_email': email, '_trial_password': password})
    a, b = users
    role = sql("SELECT rolbypassrls FROM pg_roles WHERE rolname='authenticated'")
    rls = sql("SELECT relrowsecurity FROM pg_class WHERE oid='public.trial_posts'::regclass")
    check('rls_and_non_bypass_role', role == 'f' and rls == 't')
    function_contract = json.loads(sql("""SELECT json_build_object(
      'security_definer', p.prosecdef, 'settings', p.proconfig,
      'owner', pg_get_userbyid(p.proowner),
      'anon_can_execute', has_function_privilege('anon', p.oid, 'EXECUTE'),
      'authenticated_can_execute', has_function_privilege('authenticated', p.oid, 'EXECUTE'))
      FROM pg_proc p WHERE p.oid='public.trial_soft_delete(uuid)'::regprocedure"""))
    function_body = sql("SELECT prosrc FROM pg_proc WHERE oid='public.trial_soft_delete(uuid)'::regprocedure")
    expected_body = Path(__file__).with_name('002_soft_delete.sql').read_text().split('$$')[1].strip()
    body_matches = function_body == expected_body
    check('installed_rpc_contract', function_contract['security_definer'] is True and
          function_contract['settings'] == ['search_path=""'] and
          function_contract['owner'] == 'postgres' and
          function_contract['anon_can_execute'] is False and
          function_contract['authenticated_can_execute'] is True and body_matches,
          **function_contract, installed_body_matches_source=body_matches,
          installed_body_sha256=hashlib.sha256(function_body.encode()).hexdigest())
    status, rows = api('POST', '/rest/v1/trial_posts',
                       {'author_id': a['user']['id'], 'body': 'owner original'}, a['access_token'], True)
    check('owner_insert', status == 201 and len(rows) == 1, http=status)
    post_id = rows[0]['id']
    uuid.UUID(post_id)
    path = '/rest/v1/trial_posts?id=eq.' + post_id
    status, rows = api('PATCH', path, {'body': 'owner changed'}, a['access_token'], True)
    check('owner_update', status == 200 and len(rows) == 1, http=status)
    status, rows = api('PATCH', path, {'body': 'attacker changed'}, b['access_token'], True)
    body = sql("SELECT body FROM public.trial_posts WHERE id='" + post_id + "'")
    check('other_update_zero_rows_unchanged', status == 200 and rows == [] and
          body == 'owner changed', http=status, affected_rows=len(rows))
    for label, user in [('owner', a), ('other', b)]:
        status, rows = api('DELETE', path, jwt=user['access_token'], returning=True)
        count = sql("SELECT count(*) FROM public.trial_posts WHERE id='" + post_id + "'")
        check(label + '_physical_delete_denied', status == 200 and rows == [] and count == '1',
              http=status, affected_rows=len(rows))
    status, response = api('POST', '/rest/v1/trial_posts',
                            {'author_id': b['user']['id'], 'body': 'impersonation'}, a['access_token'], True)
    check('impersonation_insert_denied', status == 403 and response.get('code') == '42501', http=status)
    status, rows = api('PATCH', path, {'deleted_at': datetime.now(timezone.utc).isoformat()},
                       a['access_token'], True)
    deleted = sql("SELECT deleted_at IS NOT NULL FROM public.trial_posts WHERE id='" + post_id + "'")
    check('soft_delete_representation_denied_by_hidden_new_row', status == 403 and
          isinstance(rows, dict) and rows.get('code') == '42501' and deleted == 'f',
          http=status, db_deleted=deleted == 't',
          error_code=rows.get('code') if isinstance(rows, dict) else None)
    status, rows = api('PATCH', path, {'deleted_at': datetime.now(timezone.utc).isoformat()},
                       a['access_token'])
    deleted = sql("SELECT deleted_at IS NOT NULL FROM public.trial_posts WHERE id='" + post_id + "'")
    check('soft_delete_minimal_also_denied_by_hidden_new_row', status == 403 and
          isinstance(rows, dict) and rows.get('code') == '42501' and deleted == 'f', http=status,
          db_deleted=deleted == 't')
    for label, user, expected in [('other', b, 0), ('owner', a, 1)]:
        status, count = api('POST', '/rest/v1/rpc/trial_soft_delete',
                             {'target_id': post_id}, user['access_token'])
        deleted = sql("SELECT deleted_at IS NOT NULL FROM public.trial_posts WHERE id='" + post_id + "'")
        check(label + '_soft_delete_rpc', status == 200 and count == expected and
              deleted == ('t' if expected else 'f'), http=status,
              affected_rows=count if type(count) is int else None,
              db_deleted=deleted == 't')
    status, rows = api('GET', path, jwt=a['access_token'])
    check('deleted_row_hidden_from_owner', status == 200 and rows == [], http=status)
    status, rows = api('GET', path, jwt=b['access_token'])
    check('deleted_row_hidden_from_other', status == 200 and rows == [], http=status)
    count = sql("SELECT count(*) FROM public.trial_posts WHERE id='" + post_id + "'")
    check('soft_deleted_physical_row_retained', count == '1', physical_rows=int(count))
    status, rows = api('POST', '/rest/v1/rpc/trial_soft_delete', {'target_id': post_id})
    check('anonymous_rpc_denied', status in (401, 403) and
          isinstance(rows, dict) and rows.get('code') == '42501', http=status,
          error_code=rows.get('code') if isinstance(rows, dict) else None)
    status, refreshed = api('POST', '/auth/v1/token?grant_type=refresh_token',
                            {'refresh_token': a['refresh_token']})
    check('refresh_endpoint', status == 200 and bool(refreshed.get('access_token')), http=status)
    status, _ = api('POST', '/auth/v1/recover', {'email': a['_trial_email']})
    check('local_recovery_email_requested', status == 200, http=status)
    recovered, recovery = mail_link(a['_trial_email'], 'recovery')
    recovery_token = recovery.get('access_token', [''])[0]
    check('local_recovery_link', recovered and bool(recovery_token))
    new_password = secrets.token_urlsafe(24)
    status, _ = api('PUT', '/auth/v1/user', {'password': new_password}, recovery_token)
    check('local_password_updated', status == 200, http=status)
    status, rejected = api('POST', '/auth/v1/token?grant_type=password',
                    {'email': a['_trial_email'], 'password': a['_trial_password']})
    check('old_password_rejected', status == 400 and rejected.get('error_code') == 'invalid_credentials',
          http=status, error_code=rejected.get('error_code'))
    status, login = api('POST', '/auth/v1/token?grant_type=password',
                        {'email': a['_trial_email'], 'password': new_password})
    check('new_password_login', status == 200 and login.get('user', {}).get('id') == a['user']['id'],
          http=status)
    report = {
        'scope': 'LOCAL_AUTH_AND_POSTGREST_TRIAL_NON_G6_NON_D4',
        'started_at_utc': started_at,
        'completed_at_utc': datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'migration_sha256': hashlib.sha256(Path(__file__).with_name('001_posts.sql').read_bytes()).hexdigest(),
        'source_sha256': {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                          for name in ('001_posts.sql', '002_soft_delete.sql', 'measure.py')},
        'checks': checks,
        'all_measured_checks_pass': all(x['passed'] for x in checks),
        'not_measured': ['external_email_delivery', 'hosted_rate_limit', 'app_deep_link',
                         'app_session_restore', 'G6_independent_execution', 'D4_authoring_effort'],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'checks': len(checks), 'passed': sum(x['passed'] for x in checks),
                      'failed': [x['name'] for x in checks if not x['passed']]}, ensure_ascii=False))
    raise SystemExit(0 if report['all_measured_checks_pass'] else 2)


if __name__ == '__main__':
    main()
