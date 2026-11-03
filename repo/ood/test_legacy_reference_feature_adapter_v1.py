"""The actual old numerical translator with synthetic causal target streams."""
import copy
import unittest
import legacy_reference_feature_adapter_v1 as m
import legacy_reference_sample_prepare_v1 as prep
import issue27ckda_d0_resource_pilot_v1 as translator
from test_legacy_reference_sample_prepare_v1 import row as partial_row,A,B


def row(*args,**kwargs):
    result={k:'' for k in translator.TSHARK_FIELDS}
    result.update(partial_row(*args,**kwargs))
    return result


class FeatureAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.api,cls.prefix,_=prep.old.legacy_runtime()

    def target(self,r):
        e=self.api.event_from_tshark(r);key=prep.guard.prefix_namespace(owner_mac=A,capture_id='s',event=e)
        return dict(source_sha256='synthetic',capture_id='s',frame=int(r['frame.number']),owner=A,session_id=prep.digest(key),
            timestamp=e.timestamp,uid=prep.digest(['synthetic',int(r['frame.number']),A]),label=0)

    def run_flows(self,rows,targets):
        return m.selected_flows(rows,targets,dict(sha256='synthetic',capture_id='s',provenance='normal'),[A,B],self.api,self.prefix,translator)

    def test_future_and_other_device_do_not_change_target(self):
        first=row(1,1);other=row(2,2,dst_mac=B);later=row(3,3)
        baseline=list(self.run_flows([first],[self.target(first)]))[0]
        with_future=list(self.run_flows([first,other,later],[self.target(first)]))[0]
        self.assertEqual(baseline,with_future)
        flows=list(self.run_flows([first,other,later],[self.target(first),self.target(later)]))
        self.assertEqual(flows[1][1]['counts'],[1,1])
        self.assertEqual(set(flows[0][1]),m.E3_KEYS)

    def test_same_device_unselected_past_is_retained(self):
        a=row(1,1);b=row(2,2)
        result=list(self.run_flows([a,b],[self.target(b)]))[0][1]
        self.assertEqual(result['counts'],[1,1]);self.assertEqual(result['flow_duration'],1000000)

    def test_bad_uid_or_label_is_rejected(self):
        a=row(1,1);target=self.target(a);target['label']=1
        with self.assertRaisesRegex(RuntimeError,'label drift'):list(self.run_flows([a],[target]))
        target=self.target(a);target['uid']='wrong'
        with self.assertRaisesRegex(RuntimeError,'UID/time'):list(self.run_flows([a],[target]))

    def test_later_regression_cannot_mutate_prior_flow(self):
        a=row(1,2);b=row(2,1)
        generator=self.run_flows([a,b],[self.target(a)])
        first=next(generator);saved=copy.deepcopy(first)
        self.assertEqual(list(generator),[]);self.assertEqual(first,saved)
        with self.assertRaisesRegex(RuntimeError,'scope or causal'):list(self.run_flows([a,b],[self.target(b)]))


if __name__=='__main__':unittest.main(verbosity=2)
