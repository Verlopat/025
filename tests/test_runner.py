import unittest,tempfile
from pathlib import Path
from sccompile.experiments import run_all
from sccompile.plot import create_figures

class RunnerTests(unittest.TestCase):
    def test_smoke(self):
        with tempfile.TemporaryDirectory() as t:
            directory=Path(t)
            data=run_all(directory,{'size':8,'seeds':1,'e7_n':4,'max_exhaustive':256},['e1','e4'])
            self.assertTrue((directory/'trials.csv').exists())
            self.assertGreater(len(data['counts']),0)
            pictures=create_figures(directory/'trials.csv',directory/'figures')
            self.assertEqual(len(pictures),5)
