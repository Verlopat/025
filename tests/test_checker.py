import json
import unittest
from verify.operational import explore, store_buffering_litmus, run_suite
from verify.history_checker import check

class CheckerTests(unittest.TestCase):
    def test_sc_litmus(self):
        self.assertFalse(store_buffering_litmus("sc")["permits_0_0"])
    def test_tso_litmus(self):
        self.assertTrue(store_buffering_litmus("tso")["permits_0_0"])
    def test_cas_model(self):
        for model in ("sc","tso"):
            result=explore(3,model=model,max_states=10000)
            self.assertEqual(result["status"],"no_counterexample_within_bounds")
    def test_unsafe_negative_control(self):
        e=explore(5,[[('unite',4,3)],[('unite',4,2)]],unsafe=True,max_states=10000)
        self.assertEqual(e["status"],"counterexample")
    def test_serial_linearizable(self):
        events=[dict(start=0,end=1,op="unite",x=2,y=1,result=1),
                dict(start=2,end=3,op="find",x=2,y=0,result=1)]
        self.assertTrue(check(events,3)["linearizable"])
    def test_impossible_result(self):
        events=[dict(start=0,end=1,op="find",x=1,y=0,result=0)]
        self.assertFalse(check(events,3)["linearizable"])
    def test_realtime(self):
        events=[dict(start=0,end=1,op="find",x=1,y=0,result=0),
                dict(start=2,end=3,op="unite",x=1,y=0,result=1)]
        self.assertFalse(check(events,3)["linearizable"])

if __name__=="__main__":unittest.main()
