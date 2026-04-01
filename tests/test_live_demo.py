from __future__ import annotations

import unittest

from mpac.live.demo import CoordinationDemo, DemoConfig


class FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)

    def complete_json(self, *, system: str, prompt: str, temperature: float = 0.2):
        if not self._responses:
            raise AssertionError("No fake response left for prompt")
        return self._responses.pop(0)


class LiveDemoTests(unittest.TestCase):
    def test_run_round_detects_conflict_and_suggests_resolution(self) -> None:
        llm = FakeLLM(
            [
                {
                    "objective": "Draft the dashboard API contract",
                    "intent_summary": "Writing the shared API contract",
                    "scope_resources": ["api/dashboard.openapi.yaml"],
                    "assumptions": ["cursor pagination"],
                    "target": "api/dashboard.openapi.yaml",
                    "op_kind": "edit",
                    "summary": "Adds dashboard schemas and endpoints.",
                    "change_ref": "draft:builder",
                    "state_ref_after": "contract:v1",
                },
                {
                    "objective": "Extend the same API contract for widget types",
                    "intent_summary": "Adding frontend metadata to the shared contract",
                    "scope_resources": ["api/dashboard.openapi.yaml"],
                    "assumptions": ["cursor pagination"],
                    "target": "api/dashboard.openapi.yaml",
                    "op_kind": "edit",
                    "summary": "Adds frontend widget metadata.",
                    "change_ref": "draft:reviewer",
                    "state_ref_after": "contract:v2",
                },
                {
                    "accepted_ids": ["op-builder-choice"],
                    "rejected_ids": ["op-reviewer-choice"],
                    "rationale": "Choose one writer for the shared contract.",
                },
            ]
        )
        demo = CoordinationDemo(
            llm,
            DemoConfig(
                agent_specs=[
                    {"id": "agent:builder", "name": "Builder", "style": "Fast implementation"},
                    {"id": "agent:reviewer", "name": "Reviewer", "style": "Risk focused"},
                ]
            ),
        )

        result = demo.run_round(task="Coordinate a dashboard API change", shared_targets=["api/dashboard.openapi.yaml"])

        self.assertEqual(len(result["plans"]), 2)
        self.assertTrue(result["resolution_suggestion"])
        self.assertEqual(len(result["snapshot"]["conflicts"]), 2)

    def test_resolution_commits_accepted_operation(self) -> None:
        llm = FakeLLM(
            [
                {
                    "objective": "Builder path",
                    "scope_resources": ["shared/file.md"],
                    "assumptions": ["assume x"],
                    "target": "shared/file.md",
                    "op_kind": "edit",
                    "summary": "Builder proposal",
                    "change_ref": "draft:one",
                    "state_ref_after": "after:one",
                },
                {
                    "objective": "Reviewer path",
                    "scope_resources": ["shared/file.md"],
                    "assumptions": ["assume x"],
                    "target": "shared/file.md",
                    "op_kind": "edit",
                    "summary": "Reviewer proposal",
                    "change_ref": "draft:two",
                    "state_ref_after": "after:two",
                },
                {
                    "accepted_ids": [],
                    "rejected_ids": [],
                    "rationale": "Fallback to first op",
                },
            ]
        )
        demo = CoordinationDemo(llm)
        result = demo.run_round(task="Coordinate", shared_targets=["shared/file.md"])
        suggestion = result["resolution_suggestion"]
        self.assertIsNotNone(suggestion)

        conflict_id = suggestion["conflict_id"]
        accepted = suggestion["accepted_ids"]
        rejected = suggestion["rejected_ids"]
        resolved = demo.resolve_conflict(
            conflict_id=conflict_id,
            accepted_ids=accepted,
            rejected_ids=rejected,
            rationale=suggestion["rationale"],
        )

        shared_state = resolved["snapshot"]["shared_state"]
        self.assertIn("shared/file.md", shared_state)


if __name__ == "__main__":
    unittest.main()
