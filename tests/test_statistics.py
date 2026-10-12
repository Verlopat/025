import unittest
from sccompile.statistics import paired_summary,holm
class StatisticsTests(unittest.TestCase):
    def test_pairs(self):
        s=paired_summary([1,2,3],[2,3,4],resamples=100)
        self.assertEqual(s['median_difference_b_minus_a'],1)
        self.assertEqual(s['pairs'],3)
        self.assertEqual(holm([.01,.03]),[.02,.03])
