from __future__ import annotations

import unittest

from mpac.live.guided_scenarios import create_guided_session, list_guided_scenarios


class GuidedScenarioTests(unittest.TestCase):
    def test_lists_five_guided_scenarios(self) -> None:
        items = list_guided_scenarios()
        self.assertEqual(len(items), 5)

    def test_scenario_one_completes_with_closed_conflict(self) -> None:
        session = create_guided_session("scenario-1")
        while not session.to_dict()["completed"]:
            session.advance()
        snapshot = session.to_dict()["snapshot"]
        self.assertEqual(snapshot["conflicts"]["conf-id-type"]["state"], "CLOSED")
        self.assertEqual(snapshot["operations"]["op-endpoint"]["state"], "COMMITTED")


if __name__ == "__main__":
    unittest.main()
