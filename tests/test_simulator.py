import unittest
from itertools import product
from sccompile.graphs import make_graph
from sccompile.certificates import compile_certificate
from sccompile.simulator import simulate

class SimulatorTests(unittest.TestCase):
    def test_path_exact_bound(self):
        for n in range(2,14):
            g=make_graph('path',n)
            x=(0,)+(1,)*(n-1)
            m=simulate(g,x,'p1')
            self.assertEqual(m.stabilization_round,n-1)
    def test_all_small_inputs(self):
        g=make_graph('path',5)
        for x in product((0,1),repeat=5):
            m=simulate(g,x,'p1')
            self.assertEqual(m.stabilization_round,m.predicted_min_round)
            self.assertTrue(m.stable_agreement)
        for name in ('c1_global_min','c2_rooted_min','c3_lex_witness','c4_cut','c5_lookup'):
            c,_=compile_certificate(g,(0,1),{'kind':name},validate_cases=256)
            for x in product((0,1),repeat=5):
                m=simulate(g,x,'p2',c)
                self.assertTrue(m.stable_agreement)
                self.assertEqual(m.selected,c.full_decision(x))
    def test_bad_intersection(self):
        g=make_graph('path',4)
        m=simulate(g,(0,1,1,1),'b5_intersection')
        self.assertFalse(m.stable_agreement)
