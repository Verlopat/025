import unittest
from itertools import product
from sccompile.graphs import make_graph
from sccompile.certificates import compile_certificate

class CertificateTests(unittest.TestCase):
    def test_exact_exhaustive(self):
        for family in ('path','cycle'):
            g=make_graph(family,4)
            for name in ('c1_global_min','c2_rooted_min','c3_lex_witness','c4_cut','c5_lookup'):
                cert,verdict=compile_certificate(g,(0,1,2),{'kind':name,'params':{'max_rows':10000}},validate_cases=10000)
                self.assertEqual(verdict['status'],'exhaustive_pass')
                for x in product((0,1,2),repeat=4):
                    self.assertIn(cert.full_decision(x),x)
    def test_c5_limit(self):
        with self.assertRaises(ValueError):
            compile_certificate(make_graph('path',8),(0,1,2),{'kind':'c5_lookup'})
    def test_witness_in_safe(self):
        g=make_graph('path',4)
        cert,_=compile_certificate(g,(0,1),{'kind':'c2_rooted_min'},validate_cases=0)
        self.assertEqual(cert.evaluate({0:0})['safe'],[0])
