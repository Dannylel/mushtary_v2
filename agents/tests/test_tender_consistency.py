import unittest
from unittest.mock import patch

from agents.buyer_form import Deliverable, TenderBuyerForm, TimelineItem
from agents.tender_consistency import reconcile_tender
from agents.tender_drafting.schemas import DRAFT_FALLBACK, TenderDeliverable, TenderMilestone


class TestTenderConsistency(unittest.TestCase):
    def _form(self):
        return TenderBuyerForm(
            tender_title="Test", tender_id="TND-1", buyer_name="Buyer", buyer_description="Buyer",
            category="Information Technology", subcategory="Infrastructure", project_objective="Objective",
            scope_of_work="Scope", deliverables=[Deliverable(name="Buyer deliverable", description="Buyer description", format="PDF")],
            timeline=[TimelineItem(milestone="Buyer milestone", date="Within 10 days")],
            roles_and_responsibilities=[], payment_terms="Terms", eligibility_criteria=[],
            submission_deadline="Tomorrow", submission_method="Platform", proposal_format="PDF",
        )

    @patch("agents.tender_consistency._agent_review", return_value=([], "deterministic_fallback"))
    def test_buyer_deliverables_and_timeline_replace_generated_conflicts(self, _review):
        draft = DRAFT_FALLBACK.model_copy(deep=True)
        draft.deliverables.deliverables = [TenderDeliverable(name="Generated", description="Different")]
        draft.timeline.milestones = [TenderMilestone(phase="", milestone="Generated", target_date="15 days")]
        reconciled, report = reconcile_tender(draft, self._form())
        self.assertEqual(reconciled.deliverables.deliverables[0].name, "Buyer deliverable")
        self.assertEqual(reconciled.timeline.milestones[0].target_date, "Within 10 days")
        self.assertEqual(report["status"], "READY_FOR_BUYER_REVIEW")

