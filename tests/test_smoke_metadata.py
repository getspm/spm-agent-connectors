from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATH = ROOT / "plugins" / "spm-codex" / "scripts" / "smoke_spm_remote_mcp.py"
SPEC = importlib.util.spec_from_file_location("spm_public_connector_smoke", SMOKE_PATH)
assert SPEC is not None and SPEC.loader is not None
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


class RemoteMetadataContractTests(unittest.TestCase):
    def metadata(self) -> dict[str, object]:
        return {
            "kind": "spm.remote_mcp_metadata",
            "requires_auth": True,
            "tools": [{"name": name} for name in sorted(SMOKE.REQUIRED_TOOLS)],
            "security": {
                "project_scoped": "supported",
                "secret_return": False,
                "billing_tools_exposed": False,
                "checkout_tools_exposed": False,
                "destructive_admin_tools_exposed": False,
                "event_bodies": "summaries_only",
                "org_scoped_project_resolution": True,
                "selected_project_set": "supported",
                "default_project_behavior": "active_project_only",
                "cross_project_behavior": "explicit_request_required",
                "external_project_mounts": "supported_with_live_boundary_enforcement",
            },
        }

    def test_accepts_scope_aware_metadata(self) -> None:
        metadata = json.loads(json.dumps(self.metadata()))
        self.assertEqual(SMOKE.validate_metadata(metadata), [])

    def test_rejects_implicit_cross_project_behavior(self) -> None:
        metadata = self.metadata()
        metadata["security"]["cross_project_behavior"] = "automatic"

        errors = SMOKE.validate_metadata(metadata)

        self.assertIn(
            "metadata security.cross_project_behavior expected 'explicit_request_required'",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
