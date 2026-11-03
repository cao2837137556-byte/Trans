"""Synthetic global-time and process cleanup boundaries; no network or models."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock,patch

import pipeline


class PipelineChecks(unittest.TestCase):
    def test_queue_time_is_excluded_and_roundtrip_is_charged_conservatively(self):
        clock=[100.];budget=pipeline.BudgetDeadline(clock=lambda:clock[0]);budget.observe({},90.)
        self.assertIsNone(budget.guard())
        budget.observe(dict(budget_remaining_seconds=17500,encoding_started_utc='synthetic'),95.)
        self.assertEqual(budget.guard(),17495.)

    def test_new_status_can_shorten_but_never_extend_the_local_deadline(self):
        clock=[100.];budget=pipeline.BudgetDeadline(clock=lambda:clock[0])
        budget.observe(dict(budget_remaining_seconds=17000),100.);first=budget.deadline
        budget.observe(dict(budget_remaining_seconds=17900),101.);self.assertEqual(budget.deadline,first)
        budget.observe(dict(budget_remaining_seconds=16000),101.);self.assertLess(budget.deadline,first)

    def test_started_status_requires_remote_budget_and_bad_times_fail(self):
        for remaining in (float('nan'),float('inf'),-1,18001,True):
            with self.subTest(remaining=remaining),self.assertRaises(ValueError):
                pipeline.BudgetDeadline().observe(dict(budget_remaining_seconds=remaining),0)
        with self.assertRaisesRegex(ValueError,'WITHOUT_GLOBAL_DEADLINE'):
            pipeline.BudgetDeadline().observe({'STATUS.json':dict(started_utc='synthetic')},0)

    def test_expired_deadline_cannot_start_another_stage(self):
        budget=pipeline.BudgetDeadline(clock=lambda:100.);budget.deadline=99.
        with patch.object(pipeline.subprocess,'Popen') as launch:
            with self.assertRaisesRegex(ValueError,'GLOBAL_ADDITIONAL'):
                pipeline.local_stage(['run.py'],'LOCAL_EVALUATION',budget)
        launch.assert_not_called()

    def test_local_stage_always_cleans_group_on_success(self):
        with tempfile.TemporaryDirectory() as td:
            child=MagicMock();child.poll.side_effect=[None,0];child.returncode=0;budget=MagicMock();budget.guard.return_value=10.
            with patch.object(pipeline,'HERE',Path(td)),patch.object(pipeline,'PACKAGE',Path(td)),\
                    patch.object(pipeline,'progress'),patch.object(pipeline.subprocess,'Popen',return_value=child),\
                    patch.object(pipeline,'descendants',return_value=[]),patch.object(pipeline.time,'sleep'),\
                    patch.object(pipeline,'stop_local_group') as cleanup:
                pipeline.local_stage(['synthetic'],'LOCAL_EVALUATION',budget)
            cleanup.assert_called_once_with(child,{})

    def test_local_stage_kills_group_on_budget_failure(self):
        with tempfile.TemporaryDirectory() as td:
            child=MagicMock();child.poll.return_value=None;budget=MagicMock();budget.guard.side_effect=[10.,ValueError('synthetic global budget')]
            with patch.object(pipeline,'HERE',Path(td)),patch.object(pipeline,'PACKAGE',Path(td)),\
                    patch.object(pipeline,'progress'),patch.object(pipeline.subprocess,'Popen',return_value=child),\
                    patch.object(pipeline,'descendants',return_value=[]),patch.object(pipeline,'stop_local_group') as cleanup:
                with self.assertRaisesRegex(ValueError,'synthetic global budget'):
                    pipeline.local_stage(['synthetic'],'LOCAL_EVALUATION',budget)
            cleanup.assert_called_once_with(child,{})

    def test_pipeline_does_not_repeat_an_uncertain_submit(self):
        with tempfile.TemporaryDirectory() as td:
            calls=[]
            def request(route,*args,**kwargs):
                calls.append(route)
                if route=='submit':raise TimeoutError('synthetic uncertain submit')
                return dict(status='PREFLIGHT_PASS')
            with patch.object(pipeline,'HERE',Path(td)),patch.object(pipeline,'PACKAGE',Path(td)),\
                    patch.object(pipeline,'progress'),patch.object(pipeline,'read',return_value=dict(execution_card_sha256='same')),\
                    patch.object(pipeline,'sha',return_value='same'),patch.object(pipeline,'write'),\
                    patch.object(pipeline,'upload'),patch.object(pipeline,'request',side_effect=request),\
                    patch.object(pipeline,'retrieve') as retrieve,patch.object(pipeline,'local_stage') as local:
                with self.assertRaises(TimeoutError):pipeline.main()
            self.assertEqual(calls.count('submit'),1);retrieve.assert_not_called();local.assert_not_called()

    def test_global_receipt_includes_non_compute_overhead(self):
        clock=[200.];budget=pipeline.BudgetDeadline(clock=lambda:clock[0]);budget.observe(dict(budget_remaining_seconds=17000),100.)
        receipt=budget.receipt();self.assertEqual(receipt['conservative_additional_wall_seconds'],1100.)
        self.assertTrue(receipt['includes_retrieval_evaluation_independent_verification'])


if __name__=='__main__':unittest.main(verbosity=2)
