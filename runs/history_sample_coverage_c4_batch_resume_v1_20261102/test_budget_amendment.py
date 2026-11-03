"""Synthetic budget/receipt boundaries; no models, real arrays or distances."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run
import verify_result


def card():
    return dict(limits=dict(total_wall_seconds=46861,encoded=37442),pair_limit=10**9,
        recovery=dict(prior_wall_seconds_charged=28861,additional_wall_seconds=18000,
            prior_encoded_rows_charged=25154,reused_encoded_rows=20480,new_encoded_rows=12288))


def encoded():
    result=dict(status='C4_ENCODING_COMPLETE',prior_encoded_rows_charged=25154,reused_encoded_rows=20480,
        new_encoded_rows_charged=12288,AB_evaluations=0,model_training=0)
    required={f'history/{key}/encoded/references.npz':'digest' for key in run.TARGETS}
    required.update({'history/NETATMO/encoded/queries.npz':'digest','history/NETATMO/encoded/DEV_LOGITS.npz':'digest','RESULT.json':'digest'})
    receipt=dict(technical_status='COMPLETED',scientific_status='C4_ENCODING_COMPLETE',mode='execute',synthetic=False,
        automatic_retry=False,pairs=0,encoded_rows=37442,elapsed_seconds=7000.,outputs=required,
        limits=dict(wall_seconds=18000,encoded=37442,cpu=4,rss_bytes=8*2**30,output_bytes=20*2**30))
    return result,receipt


class BudgetAmendmentChecks(unittest.TestCase):
    def test_attempt_ceiling_includes_discarded_rows_without_double_charging_reuse(self):
        p=run.budget_plan(card())
        self.assertEqual(p['discarded_previous_charged_rows'],4674)
        self.assertEqual(p['prior_encoded_rows_charged']+p['new_encoded_rows'],37442)
        self.assertNotEqual(p['reused_encoded_rows']+p['new_encoded_rows'],37442)

    def test_new_allowance_is_exactly_18000_seconds(self):
        self.assertEqual(run.remaining_wall_seconds(card()),18000)
        self.assertEqual(run.remaining_wall_seconds(card(),dict(elapsed_seconds=7000),dict(elapsed_seconds=1000)),10000)

    def test_previous_and_new_attempt_counts_must_reconcile(self):
        for location,key,value in (('limits','encoded',36864),('limits','total_wall_seconds',46860),
                ('recovery','prior_encoded_rows_charged',20480),('recovery','prior_wall_seconds_charged',28800)):
            c=card();c[location][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):run.budget_plan(c)

    def test_nan_infinite_negative_and_exhausted_wall_budgets_fail(self):
        for seconds in (float('nan'),float('inf'),-1,18000,18001,True):
            with self.subTest(seconds=seconds),self.assertRaises(ValueError):
                run.remaining_wall_seconds(card(),dict(elapsed_seconds=seconds))

    def test_real_completed_encoding_receipt_passes(self):
        result,receipt=encoded()
        self.assertEqual(run.validate_encoding_receipt(card(),result,receipt)['remaining_after_encoding_seconds'],11000)

    def test_partial_synthetic_wrong_charges_and_distances_fail(self):
        result,receipt=encoded()
        for key,value in (('technical_status','EXCEPTION_STOPPED'),('synthetic',True),('mode','check'),
                ('automatic_retry',True),('encoded_rows',32768),('pairs',1)):
            modified=copy.deepcopy(receipt);modified[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                run.validate_encoding_receipt(card(),result,modified)

    def test_missing_netatmo_development_logits_is_not_complete(self):
        result,receipt=encoded();del receipt['outputs']['history/NETATMO/encoded/DEV_LOGITS.npz']
        with self.assertRaises(ValueError):run.validate_encoding_receipt(card(),result,receipt)

    def test_inconsistent_new_attempt_or_hidden_ab_execution_fails(self):
        result,receipt=encoded()
        for key,value in (('new_encoded_rows_charged',12287),('prior_encoded_rows_charged',20480),
                ('AB_evaluations',1),('model_training',1)):
            modified=dict(result,**{key:value})
            with self.subTest(key=key),self.assertRaises(ValueError):
                run.validate_encoding_receipt(card(),modified,receipt)

    def test_runtime_default_is_the_amended_stage_allowance(self):
        from hnr.runtime import LIMITS
        self.assertEqual(LIMITS['encoded'],37442);self.assertEqual(LIMITS['wall_seconds'],18000)
        self.assertEqual(LIMITS['rss_bytes'],8*2**30);self.assertEqual(LIMITS['cpu'],4)

    def run_mock_verification(self,*,evaluation_seconds=1000.,verification_seconds=123.,replay_error=None):
        c=card();er,encoding_receipt=encoded();instances=[]
        evaluation_receipt=dict(technical_status='COMPLETED',scientific_status='ADOPT_C4',mode='execute',synthetic=False,
            automatic_retry=False,pairs=123456,encoded_rows=0,elapsed_seconds=evaluation_seconds,
            limits=dict(encoded=0,wall_seconds=11000,cpu=4,rss_bytes=8*2**30,output_bytes=20*2**30,pairs=10**9))
        class FakeRuntime:
            def __init__(self,output):self.output=output;self.limits={};instances.append(self)
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def update(self,*args,**kw):pass
            def finish(self,value):
                self.result=value
                return dict(elapsed_seconds=verification_seconds,encoded_rows=0,pairs=0)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);out=p/'outputs/evaluation';source=p/'retrieved'
            budget=dict(**run.validate_encoding_receipt(c,er,encoding_receipt),encoding_directory=str(source),
                execution_card_sha256='same',encoding_result_sha256='same',encoding_stage_receipt_sha256='same')
            values={out/'STAGE_RECEIPT.json':evaluation_receipt,out/'ENCODING_BUDGET_RECEIPT.json':budget,
                source/'RESULT.json':er,source/'STAGE_RECEIPT.json':encoding_receipt,
                out/'RESULT.json':dict(status='ADOPT_C4',distance_pairs=123456)}
            with patch.object(verify_result,'PACKAGE',p),patch.object(verify_result,'verify',return_value=c),\
                    patch.object(verify_result,'read',side_effect=lambda q:values[Path(q)]),\
                    patch.object(verify_result,'sha',return_value='same'),patch.object(verify_result,'Runtime',FakeRuntime),\
                    patch.object(verify_result,'write') as writing,patch.object(verify_result,'replay_saved_result',
                        return_value=dict(status='PASS',scientific_status='ADOPT_C4'),side_effect=replay_error) as replay:
                error=None
                try:verify_result.main()
                except Exception as exc:error=exc
                return instances,writing.call_args_list,replay.call_count,error

    def test_independent_verifier_has_only_remaining_time_and_zero_science_budget(self):
        instances,writes,replays,error=self.run_mock_verification()
        self.assertIsNone(error);self.assertEqual(replays,1)
        self.assertEqual(instances[0].limits,dict(wall_seconds=10000.,pairs=0,encoded=0))
        acceptance=writes[-1].args[1]
        self.assertEqual(acceptance['cumulative_charged_wall_seconds'],36984.)
        self.assertEqual(acceptance['cumulative_encoded_rows_charged'],37442)

    def test_no_verification_or_acceptance_after_wall_exhaustion(self):
        instances,writes,replays,error=self.run_mock_verification(evaluation_seconds=11000)
        self.assertIsInstance(error,ValueError);self.assertEqual(instances,[]);self.assertEqual(writes,[]);self.assertEqual(replays,0)

    def test_replay_failure_never_publishes_acceptance(self):
        instances,writes,replays,error=self.run_mock_verification(replay_error=ValueError('synthetic replay failure'))
        self.assertIsInstance(error,ValueError);self.assertEqual(writes,[]);self.assertEqual(replays,1)

    def test_final_cumulative_time_includes_verification(self):
        instances,writes,replays,error=self.run_mock_verification(verification_seconds=10001)
        self.assertIsInstance(error,ValueError);self.assertEqual(writes,[]);self.assertEqual(replays,1)


if __name__=='__main__':unittest.main(verbosity=2)
