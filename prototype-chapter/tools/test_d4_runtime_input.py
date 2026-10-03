from __future__ import annotations

import base64
import json
import unittest
from dataclasses import replace

from d4_runtime_input import (
    PUBLIC_FIELDS,
    RuntimeInputError,
    TrustedBinding,
    load_declared_public_runtime_input,
)


def jwt(role: str) -> str:
    def part(value: object) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{part({'alg': 'HS256'})}.{part({'role': role})}.signature"


class RuntimeInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.post_ids = (
            "11111111-1111-4111-8111-111111111111",
            "22222222-2222-4222-8222-222222222222",
        )
        self.binding = TrustedBinding(
            run_id="0123456789abcdef",
            chapter_sha256="a" * 64,
            start_sha256="b" * 64,
            supabase_url="http://192.168.11.11:8094",
            publishable_key="sb_publishable_public-test-value",
            auth_return_base="exp://192.168.11.11:8093/--/auth/return",
            lan_host="192.168.11.11",
            post_ids=self.post_ids,
        )
        self.value = {
            "version": 1,
            "run_id": self.binding.run_id,
            "chapter_sha256": self.binding.chapter_sha256,
            "start_sha256": self.binding.start_sha256,
            "public": {
                "EXPO_PUBLIC_SUPABASE_URL": self.binding.supabase_url,
                "EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY": self.binding.publishable_key,
                "EXPO_PUBLIC_AUTH_RETURN_BASE": self.binding.auth_return_base,
                "EXPO_PUBLIC_AUTH_TRIAL_LAN_HOST": self.binding.lan_host,
                "EXPO_PUBLIC_RLS_TRIAL_POST_IDS": ",".join(self.post_ids),
            },
        }

    def load(self, value: object | None = None, binding: TrustedBinding | None = None):
        return load_declared_public_runtime_input(
            json.dumps(self.value if value is None else value), binding or self.binding
        )

    def rejected(self, value: object) -> None:
        with self.assertRaises(RuntimeInputError):
            self.load(value)

    def test_valid_publishable_input_returns_immutable_env_and_redacted_receipt(self) -> None:
        result = self.load()
        self.assertEqual(tuple(result.env), PUBLIC_FIELDS)
        self.assertEqual(result.env[PUBLIC_FIELDS[0]], self.binding.supabase_url)
        with self.assertRaises(TypeError):
            result.env[PUBLIC_FIELDS[0]] = "https://changed.example"  # type: ignore[index]
        self.assertEqual(result.public_receipt["key_kind"], "publishable")
        self.assertEqual(result.public_receipt["run_id"], self.binding.run_id)
        rendered = repr(result.public_receipt)
        for raw in (
            self.binding.publishable_key,
            self.binding.supabase_url,
            *self.post_ids,
        ):
            self.assertNotIn(raw, rendered)

    def test_valid_legacy_anon_key_reports_legacy_kind(self) -> None:
        anon = jwt("anon")
        binding = replace(self.binding, publishable_key=anon)
        value = json.loads(json.dumps(self.value))
        value["public"]["EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY"] = anon
        result = self.load(value, binding)
        self.assertEqual(result.public_receipt["key_kind"], "legacy_anon_jwt")

    def test_valid_hosted_https_frontend_is_accepted(self) -> None:
        hosted = "https://candidate.supabase.co"
        binding = replace(self.binding, supabase_url=hosted)
        value = json.loads(json.dumps(self.value))
        value["public"]["EXPO_PUBLIC_SUPABASE_URL"] = hosted
        self.assertEqual(self.load(value, binding).env[PUBLIC_FIELDS[0]], hosted)

    def test_publishable_key_accepts_base64url_opaque_suffix(self) -> None:
        key = "sb_publishable_AZaz09_-"
        binding = replace(self.binding, publishable_key=key)
        value = json.loads(json.dumps(self.value))
        value["public"]["EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY"] = key
        self.assertEqual(
            self.load(value, binding).env["EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY"],
            key,
        )

    def test_secret_service_and_authenticated_keys_are_rejected(self) -> None:
        for key in ("sb_secret_private", jwt("service_role"), jwt("authenticated")):
            with self.subTest(key=key[:12]):
                value = json.loads(json.dumps(self.value))
                value["public"]["EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY"] = key
                with self.assertRaises(RuntimeInputError):
                    self.load(value, replace(self.binding, publishable_key=key))

    def test_every_runtime_value_must_match_controller_binding(self) -> None:
        replacements = {
            "EXPO_PUBLIC_SUPABASE_URL": "https://different.example",
            "EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY": "sb_publishable_other",
            "EXPO_PUBLIC_AUTH_RETURN_BASE": "exp://192.168.11.12:8093/--/auth/return",
            "EXPO_PUBLIC_AUTH_TRIAL_LAN_HOST": "192.168.11.12",
            "EXPO_PUBLIC_RLS_TRIAL_POST_IDS": (
                "33333333-3333-4333-8333-333333333333," + self.post_ids[1]
            ),
        }
        for field, changed in replacements.items():
            with self.subTest(field=field):
                value = json.loads(json.dumps(self.value))
                value["public"][field] = changed
                self.rejected(value)

    def test_missing_extra_and_private_fields_are_rejected(self) -> None:
        missing_top = json.loads(json.dumps(self.value))
        del missing_top["run_id"]
        missing_public = json.loads(json.dumps(self.value))
        del missing_public["public"][PUBLIC_FIELDS[0]]
        extra_top = json.loads(json.dumps(self.value))
        extra_top["session"] = "forbidden"
        for extra in (
            "actors",
            "email",
            "jwt_session",
            "password",
            "private",
            "service_role_key",
        ):
            value = json.loads(json.dumps(self.value))
            value["public"][extra] = "not-allowed"
            self.rejected(value)
        self.rejected(missing_top)
        self.rejected(missing_public)
        self.rejected(extra_top)

    def test_duplicate_fields_and_nan_are_rejected(self) -> None:
        raw = json.dumps(self.value)
        duplicate = raw.replace('"version": 1,', '"version": 1, "version": 1,', 1)
        with self.assertRaises(RuntimeInputError):
            load_declared_public_runtime_input(duplicate, self.binding)
        nested = raw.replace(
            '"EXPO_PUBLIC_SUPABASE_URL":',
            '"EXPO_PUBLIC_SUPABASE_URL": "http://127.0.0.1", "EXPO_PUBLIC_SUPABASE_URL":',
            1,
        )
        with self.assertRaises(RuntimeInputError):
            load_declared_public_runtime_input(nested, self.binding)
        with self.assertRaises(RuntimeInputError):
            load_declared_public_runtime_input(raw.replace('"version": 1', '"version": NaN'), self.binding)

    def test_invalid_urls_are_rejected(self) -> None:
        cases = [
            ("EXPO_PUBLIC_SUPABASE_URL", "http://example.com"),
            ("EXPO_PUBLIC_SUPABASE_URL", "https://user@example.com"),
            ("EXPO_PUBLIC_SUPABASE_URL", "https://example.com?secret=value"),
            ("EXPO_PUBLIC_SUPABASE_URL", "ftp://192.168.11.11"),
            ("EXPO_PUBLIC_AUTH_RETURN_BASE", "https://example.com/--/auth/return"),
            ("EXPO_PUBLIC_AUTH_RETURN_BASE", "exp://192.168.11.11:8093/wrong"),
            ("EXPO_PUBLIC_AUTH_RETURN_BASE", "exp://user@192.168.11.11:8093/--/auth/return"),
        ]
        for field, invalid in cases:
            with self.subTest(field=field, invalid=invalid):
                value = json.loads(json.dumps(self.value))
                value["public"][field] = invalid
                self.rejected(value)

    def test_controls_and_internal_whitespace_are_rejected_even_when_binding_matches(self) -> None:
        cases = (
            (
                "EXPO_PUBLIC_SUPABASE_URL",
                "http://192.168.11.11:\t8094",
                replace(self.binding, supabase_url="http://192.168.11.11:\t8094"),
            ),
            (
                "EXPO_PUBLIC_SUPABASE_URL",
                "https://candidate .supabase.co",
                replace(self.binding, supabase_url="https://candidate .supabase.co"),
            ),
            (
                "EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
                "sb_publishable_public\nembedded",
                replace(self.binding, publishable_key="sb_publishable_public\nembedded"),
            ),
            (
                "EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
                "sb_publishable_public embedded",
                replace(self.binding, publishable_key="sb_publishable_public embedded"),
            ),
            (
                "EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
                "sb_publishable_public\x7fembedded",
                replace(self.binding, publishable_key="sb_publishable_public\x7fembedded"),
            ),
        )
        for field, invalid, binding in cases:
            with self.subTest(field=field, invalid=repr(invalid)):
                value = json.loads(json.dumps(self.value))
                value["public"][field] = invalid
                with self.assertRaises(RuntimeInputError):
                    self.load(value, binding)

    def test_controls_are_rejected_in_all_declared_string_positions(self) -> None:
        for field in ("run_id", "chapter_sha256", "start_sha256"):
            with self.subTest(field=field):
                value = json.loads(json.dumps(self.value))
                value[field] += "\x01"
                self.rejected(value)

    def test_same_or_noncanonical_post_ids_are_rejected(self) -> None:
        for post_ids in (
            f"{self.post_ids[0]},{self.post_ids[0]}",
            f" {self.post_ids[0]},{self.post_ids[1]}",
            "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA," + self.post_ids[1],
        ):
            with self.subTest(post_ids=post_ids):
                value = json.loads(json.dumps(self.value))
                value["public"]["EXPO_PUBLIC_RLS_TRIAL_POST_IDS"] = post_ids
                self.rejected(value)

    def test_bool_zero_wrong_types_and_hash_drift_are_rejected(self) -> None:
        for version in (True, 0, "1"):
            value = json.loads(json.dumps(self.value))
            value["version"] = version
            self.rejected(value)
        wrong_type = json.loads(json.dumps(self.value))
        wrong_type["public"][PUBLIC_FIELDS[0]] = False
        self.rejected(wrong_type)
        for field in ("chapter_sha256", "start_sha256"):
            value = json.loads(json.dumps(self.value))
            value[field] = "c" * 64
            self.rejected(value)

    def test_binding_is_also_fail_closed(self) -> None:
        with self.assertRaises(RuntimeInputError):
            self.load(binding=replace(self.binding, post_ids=(self.post_ids[0], self.post_ids[0])))
        with self.assertRaises(RuntimeInputError):
            self.load(binding=replace(self.binding, chapter_sha256="bad"))


if __name__ == "__main__":
    unittest.main()
