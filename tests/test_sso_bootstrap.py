"""The SSO bootstrap writes public PKCE redirects and secret references, without a cluster."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).parents[1]


class BrowserSsoBootstrap(unittest.TestCase):
    def test_browser_redirect_secret_and_shared_ingress_are_repeatable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            state = root / ".state"
            state.mkdir()
            (state / "sso-domain.txt").write_text("https://demo.example.test")
            for name in ("engine.yml", "ui.yml"):
                (state / name).write_text("Secrets:\n  Source_type: FILE\n  Path: /secrets/provider.env\nObject_stores:\n  demo: {}\n")
            for name in ("provider.env", "engine.env"):
                (state / name).write_text("EXISTING=value\n")
            binary = root / "bin"
            binary.mkdir()
            for name, body in (("kubectl", "#!/bin/sh\ncat >/dev/null\n"), ("uv", "#!/bin/sh\nprintf 'test-password-hash\\n'\n")):
                path = binary / name
                path.write_text(body)
                path.chmod(0o700)
            env = {**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"]}
            def bootstrap():
                subprocess.run(["sh", str(ROOT / "infra/bootstrap/sso.sh")], cwd=root,
                               env=env, check=True, capture_output=True, timeout=30)
            bootstrap()
            dex = yaml.safe_load((state / "dex.yaml").read_text())
            client = dex["staticClients"][0]
            self.assertIn("/device/callback", client["redirectURIs"])
            self.assertIn("https://demo.example.test/ui/signin/callback", client["redirectURIs"])
            self.assertTrue(client["public"])
            ui = yaml.safe_load((state / "ui.yml").read_text())
            self.assertEqual(ui["Auth"]["Browser_state_secret"], "BROWSER_STATE_SECRET")
            self.assertEqual(ui["Docs_site"]["External_url"], "https://demo.example.test")
            key = (state / "browser-state-secret").read_text()
            self.assertGreaterEqual(len(key.encode()), 32)
            self.assertEqual((state / "browser-state-secret").stat().st_mode & 0o777, 0o600)
            self.assertNotIn(key, (state / "ui.yml").read_text())
            self.assertTrue("BROWSER_STATE_SECRET=" + key in (state / "provider.env").read_text())
            self.assertEqual((root / ".env.demo-users").stat().st_mode & 0o777, 0o600)
            ingress = yaml.safe_load((state / "sso-ingress.yml").read_text())
            self.assertEqual(ingress["spec"]["rules"][0]["host"], "demo.example.test")
            self.assertEqual({p["path"] for p in ingress["spec"]["rules"][0]["http"]["paths"]}, {"/", "/dex"})
            bootstrap()
            self.assertTrue(key == (state / "browser-state-secret").read_text())
            self.assertEqual((state / "provider.env").read_text().count("BROWSER_STATE_SECRET="), 1)
