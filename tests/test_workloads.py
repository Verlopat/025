import unittest
import tempfile
from pathlib import Path
from python.workloads import operation,generate
from python.analysis import bootstrap_ci,paired_comparisons,holm

class WorkloadTests(unittest.TestCase):
    def test_all_families(self):
        for i in range(1,9):
            p=operation(f"w{i}",10,2,3,123)
            self.assertIn(p["op"],("find","unite"))
            self.assertTrue(0<=p["x"]<10 and 0<=p["y"]<10)
    def test_byte_identity(self):
        with tempfile.TemporaryDirectory() as d:
            p,q=Path(d)/"a.jsonl",Path(d)/"b.jsonl"
            generate(p,seed=7);generate(q,seed=7)
            self.assertEqual(p.read_bytes(),q.read_bytes())
    def test_holm(self):
        self.assertEqual(holm([.01,.03]),[.02,.03])
    def test_bootstrap(self):
        self.assertEqual(bootstrap_ci([2,2]),(2,2))

if __name__=="__main__":unittest.main()
