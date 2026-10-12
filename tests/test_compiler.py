import unittest
from itertools import product
from sccompile.graphs import make_graph
from sccompile.compiler import compile_protocol
from sccompile.simulator import simulate

class CompilerTests(unittest.TestCase):
    def test_message_passing_matches_central_simulator(self):
        g=make_graph('path',5)
        for kind in ('c1_global_min','c2_rooted_min','c3_lex_witness','c4_cut','c5_lookup'):
            machine=compile_protocol(g,(0,1),{'kind':kind})
            for x in product((0,1),repeat=g.n):
                states=[machine.init(i,x[i]) for i in range(g.n)]
                for _ in range(g.diameter()+1):
                    old_messages=[machine.message(s) for s in states]
                    states=[machine.transition(states[i],
                            [old_messages[j] for j in g.adj[i]]) for i in range(g.n)]
                self.assertEqual([s.output_value for s in states],[machine.full_decision(x)]*g.n)
                m=simulate(g,x,'p2',machine)
                self.assertEqual(m.selected,machine.full_decision(x))
