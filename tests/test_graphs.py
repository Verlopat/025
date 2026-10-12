import unittest
from sccompile.graphs import make_graph,from_edges
from sccompile.inputs import input_vector,derived_seed

class GraphTests(unittest.TestCase):
    def test_exact_distance(self):
        p=make_graph('path',5)
        self.assertEqual(p.diameter(),4)
        self.assertEqual(p.radius(),2)
        self.assertEqual(p.center(),2)
        self.assertEqual(make_graph('cycle',6).diameter(),3)
        self.assertEqual(make_graph('grid',9).diameter(),4)
    def test_bad_disconnected(self):
        with self.assertRaises(ValueError):from_edges(3,[(0,1)])
    def test_regular_reproducible(self):
        for d in (3,4,8):
            g=make_graph('regular',24,123,d)
            self.assertTrue(all(len(x)==d for x in g.adj))
            self.assertEqual(g,make_graph('regular',24,123,d))
    def test_seeds(self):
        g=make_graph('path',16)
        self.assertEqual(derived_seed('p',123),derived_seed('p',123))
        self.assertEqual(input_vector(g,3,'random',7),input_vector(g,3,'random',7))
