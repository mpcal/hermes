"""Run against the real adapter in the pinned/derived Hermes image; no mail is sent."""

import asyncio
import logging
import os
import tempfile
import unittest
from email.mime.text import MIMEText
from pathlib import Path
from unittest.mock import patch

import yaml

from agent import secret_scope
from gateway.config import Platform, load_gateway_config
from plugins.platforms.email.adapter import EmailAdapter


OPTION = "allow_proton_internal_without_auth_results"
SENDER = "owner@pm.me"
INTERNAL = [("X-Pm-Origin", "internal"), ("X-Pm-Content-Encryption", "end-to-end")]


class ProtonInternalEmailTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        self.env = {
            "HERMES_HOME": self.home.name,
            "EMAIL_ADDRESS": "agent@pm.me",
            "EMAIL_PASSWORD": "test-only",
            "EMAIL_IMAP_HOST": "proton-bridge",
            "EMAIL_SMTP_HOST": "proton-bridge",
            "EMAIL_ALLOWED_USERS": SENDER + ",owner@custom.example",
        }
        self.environment = patch.dict(os.environ, self.env, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        secret_scope.set_multiplex_active(False)
        self.addCleanup(secret_scope.set_multiplex_active, False)

    def adapter(self, enabled=True, home=None):
        home = Path(home or self.home.name)
        home.mkdir(parents=True, exist_ok=True)
        settings = {"enabled": True, "require_authenticated_sender": True}
        if enabled is not None:
            settings[OPTION] = enabled
        (home / "config.yaml").write_text(
            yaml.safe_dump({"platforms": {"email": settings}}), encoding="utf-8"
        )
        with patch.dict(os.environ, {"HERMES_HOME": str(home)}):
            return EmailAdapter(load_gateway_config().platforms[Platform.EMAIL])

    def message(self, adapter, headers=None, sender=SENDER):
        msg = MIMEText("Harmless test body; no actions requested.")
        if sender is not None:
            msg["From"] = sender
        msg["Subject"] = "Proton regression test"
        msg["Message-ID"] = "<test@pm.me>"
        for key, value in INTERNAL if headers is None else headers:
            msg[key] = value
        return adapter._parse_fetched_message(b"1", msg.as_bytes())

    def accepted(self, adapter, **kwargs):
        data = self.message(adapter, **kwargs)
        return data is not None and adapter._sender_accepted(data["sender_addr"], data)

    def test_allowlisted_internal_message_is_accepted_when_enabled(self):
        self.assertTrue(self.accepted(self.adapter()))

    def test_custom_domain_internal_message_is_accepted(self):
        self.assertTrue(self.accepted(self.adapter(), sender="owner@custom.example"))

    def test_default_and_explicit_false_do_not_allow_exception(self):
        for value in (None, False, "false"):
            with self.subTest(value=value):
                self.assertFalse(self.accepted(self.adapter(value)))

    def test_exception_does_not_claim_standard_authentication(self):
        data = self.message(self.adapter())
        self.assertFalse(data["sender_authenticated"])
        self.assertEqual(data["auth_reason"], "no Authentication-Results header")
        self.assertTrue(data.get("proton_internal_candidate", False))

    def test_unlisted_and_self_senders_still_rejected(self):
        adapter = self.adapter()
        for sender in ("stranger@pm.me", "agent@pm.me"):
            with self.subTest(sender=sender):
                self.assertFalse(self.accepted(adapter, sender=sender))

    def test_automated_mail_still_rejected(self):
        self.assertFalse(self.accepted(
            self.adapter(), headers=INTERNAL + [("Auto-Submitted", "auto-generated")]
        ))

    def test_missing_allowlist_still_denies_access(self):
        os.environ.pop("EMAIL_ALLOWED_USERS")
        self.assertFalse(self.accepted(self.adapter()))

    def test_malformed_or_incomplete_proton_headers_cannot_qualify(self):
        cases = [
            [], INTERNAL[:1], INTERNAL[1:],
            [("X-Pm-Origin", "external"), INTERNAL[1]],
            [INTERNAL[0], ("X-Pm-Content-Encryption", "on-receive")],
            [("X-Pm-Origin", "internal, external"), INTERNAL[1]],
            INTERNAL + [INTERNAL[0]], INTERNAL + [INTERNAL[1]],
            INTERNAL + [("X-Pm-Origin", "external")],
            INTERNAL + [("X-Pm-Content-Encryption", "none")],
        ]
        adapter = self.adapter()
        for headers in cases:
            with self.subTest(headers=headers):
                data = self.message(adapter, headers=headers)
                self.assertFalse(data.get("proton_internal_candidate", False))
                self.assertFalse(adapter._sender_accepted(data["sender_addr"], data))

    def test_any_auth_results_header_disables_exception(self):
        adapter = self.adapter()
        for result in ("", "mail.protonmail.ch; dmarc=fail", "unparseable"):
            with self.subTest(result=result):
                data = self.message(adapter, headers=INTERNAL + [("Authentication-Results", result)])
                self.assertFalse(data.get("proton_internal_candidate", False))
                self.assertFalse(adapter._sender_accepted(data["sender_addr"], data))

    def test_external_authenticated_mail_keeps_existing_behavior(self):
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                self.assertTrue(self.accepted(self.adapter(enabled), headers=[
                    ("Authentication-Results", "mail.protonmail.ch; dmarc=pass header.from=pm.me")
                ]))

    def test_external_spoofed_proton_address_is_rejected(self):
        self.assertFalse(self.accepted(self.adapter(), headers=[("X-Pm-Origin", "external")]))

    def test_missing_multiple_and_ambiguous_from_cannot_qualify(self):
        adapter = self.adapter()
        cases = [
            (None, INTERNAL),
            ("Owner <owner@pm.me>, Other <other@example.com>", INTERNAL),
            ("Owner <owner@pm.me>", INTERNAL + [("From", "other@example.com")]),
            ("Owner <owner@pm.me> trailing <other@example.com>", INTERNAL),
        ]
        for sender, headers in cases:
            with self.subTest(sender=sender, headers=headers):
                self.assertFalse(self.accepted(adapter, sender=sender, headers=headers))

    def test_display_name_case_and_folded_headers_are_supported(self):
        self.assertTrue(self.accepted(self.adapter(), sender='"Owner, Test" <OWNER@PM.ME>', headers=[
            ("x-pm-origin", " Internal "),
            ("x-pm-content-encryption", "\r\n end-to-end"),
        ]))

    def test_exception_is_logged_without_body_or_auth_pass_claim(self):
        adapter = self.adapter()
        with self.assertLogs("plugins.platforms.email.adapter", logging.INFO) as logs:
            self.assertTrue(self.accepted(adapter))
        log = "\n".join(logs.output)
        self.assertIn("Proton-internal exception", log)
        self.assertNotIn("Harmless test body", log)
        self.assertNotIn("dmarc=pass", log)

    def test_profile_config_does_not_leak_a_to_b_to_a(self):
        a = self.adapter(True, Path(self.home.name) / "a")
        b = self.adapter(None, Path(self.home.name) / "b")
        for adapter, expected in ((a, True), (b, False), (a, True)):
            self.assertEqual(self.accepted(adapter), expected)

    def test_dispatch_reaches_handler_only_for_accepted_messages(self):
        adapter = self.adapter()
        received = []

        async def receive(event):
            received.append(event.text)

        # Replace the agent/network boundary; keep parsing, authorization, and dispatch real.
        adapter.handle_message = receive
        asyncio.run(adapter._dispatch_message(self.message(adapter)))
        asyncio.run(adapter._dispatch_message(self.message(adapter, sender="stranger@pm.me")))
        self.assertEqual(received, [
            "[Subject: Proton regression test]\n\nHarmless test body; no actions requested."
        ])


if __name__ == "__main__":
    unittest.main()
