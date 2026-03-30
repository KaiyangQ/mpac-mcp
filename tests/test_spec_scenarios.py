"""Executable tests for the five Appendix A scenarios."""

from __future__ import annotations

import unittest

from mpac.scenarios import SCENARIOS, run_scenario


class SpecScenarioTests(unittest.TestCase):
    def test_scenario_1(self) -> None:
        result = run_scenario(SCENARIOS[0])
        self.assertEqual(result["snapshot"]["conflicts"]["conf-id-type"]["state"], "CLOSED")

    def test_scenario_2(self) -> None:
        result = run_scenario(SCENARIOS[1])
        self.assertEqual(result["snapshot"]["shared_state"]["paper.sections.methods"], "sha256:methods-v2-cited")

    def test_scenario_3(self) -> None:
        result = run_scenario(SCENARIOS[2])
        self.assertEqual(result["snapshot"]["operations"]["op-cache-flush"]["state"], "REJECTED")

    def test_scenario_4(self) -> None:
        result = run_scenario(SCENARIOS[3])
        self.assertEqual(result["snapshot"]["operations"]["op-api-routes-v2"]["state"], "COMMITTED")

    def test_scenario_5(self) -> None:
        result = run_scenario(SCENARIOS[4])
        self.assertEqual(result["snapshot"]["operations"]["op-final-itinerary"]["state"], "COMMITTED")


if __name__ == "__main__":
    unittest.main()
