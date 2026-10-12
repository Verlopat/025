import json
import subprocess
import unittest
from pathlib import Path
from verify.history_checker import check_file

ROOT=Path(__file__).resolve().parents[1]
BIN=ROOT/"build"/"saw_bench"
class NativeTests(unittest.TestCase):
    def test_small_linearizability_history(self):
        import tempfile
        if not BIN.exists():self.skipTest("build not available")
        with tempfile.TemporaryDirectory() as d:
            hist=Path(d)/"history.jsonl"
            proc=subprocess.run([str(BIN),"--n","4","--threads","2","--ops","2",
                                 "--variant","p1","--workload","w6","--history",str(hist)],
                                text=True,capture_output=True,check=True)
            self.assertTrue(json.loads(proc.stdout)["valid_final"])
            self.assertTrue(check_file(hist,4)["linearizable"])

if __name__=="__main__":unittest.main()
