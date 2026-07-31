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

FRESH_INSTALL_PATH = ROOT / "scripts" / "smoke_fresh_codex_install.py"
FRESH_INSTALL_SPEC = importlib.util.spec_from_file_location(
    "spm_fresh_codex_install", FRESH_INSTALL_PATH
)
assert FRESH_INSTALL_SPEC is not None and FRESH_INSTALL_SPEC.loader is not None
FRESH_INSTALL = importlib.util.module_from_spec(FRESH_INSTALL_SPEC)
FRESH_INSTALL_SPEC.loader.exec_module(FRESH_INSTALL)

HOOK_PATH = ROOT / "plugins" / "spm-codex" / "scripts" / "spm_codex_hook.py"
HOOK_SPEC = importlib.util.spec_from_file_location("spm_public_connector_hook", HOOK_PATH)
assert HOOK_SPEC is not None and HOOK_SPEC.loader is not None
HOOK = importlib.util.module_from_spec(HOOK_SPEC)
HOOK_SPEC.loader.exec_module(HOOK)


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

    def test_fresh_install_smoke_reads_the_public_plugin_version(self) -> None:
        plugin_version = json.loads(
            (ROOT / "plugins" / "spm-codex" / ".codex-plugin" / "plugin.json").read_text()
        )["version"]

        self.assertEqual(FRESH_INSTALL.expected_version(ROOT), plugin_version)

    def test_preflight_and_post_action_share_one_permission_contract(self) -> None:
        self.assertEqual(
            SMOKE.SMOKE_MCP_PERMISSIONS,
            ("objects:read", "objects:write", "agent_hardening:write"),
        )
        self.assertEqual(SMOKE.EXPECTED_ACTION_REPORT_STATUS, "valid")

    def test_compact_receipt_only_counts_aggregated_turns(self) -> None:
        receipt = {
            "kind": "spm.agent_memory_capture_receipt",
            "journal_status": "recorded",
            "persistence_status": "applied",
            "project_id": "e2de5034-ac68-4251-befa-2d873172120b",
            "project_name": "SPM Demo - Agent Memory Infrastructure",
            "temporal_layer": "current",
            "entry_hash": "39862cbda046abcdef",
            "display_language": "es",
            "source_message": "entrada guardada",
            "memory_message": "memoria del proyecto actualizada",
        }

        single = HOOK._receipt_summary("compact", [receipt])
        aggregated = HOOK._receipt_summary("compact", [receipt, receipt])

        self.assertNotIn("turno", single)
        self.assertIn("2 turnos capturados", aggregated)
        self.assertNotIn("turns", HOOK._prompt_receipt_facts("compact", receipt))


if __name__ == "__main__":
    unittest.main()
