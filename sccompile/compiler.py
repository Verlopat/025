"""Executable compiler API for finite decision certificates.

CompiledProtocol is an emitted local machine with init/message/transition/output;
it never reads inputs of distant processes except through received messages.
"""
from __future__ import annotations
from dataclasses import dataclass
from .certificates import compile_certificate

@dataclass
class LocalState:
    node:int
    own_input:int
    view:dict[int,int]
    output_value:int
    round:int=0

class CompiledProtocol:
    def __init__(self,certificate,validation):
        self.certificate=certificate;self.validation=validation
        self.graph=certificate.graph
        self.alphabet=certificate.alphabet
        self.kind=certificate.kind

    def init(self,node,value):
        if not 0<=node<self.graph.n or value not in self.alphabet:
            raise ValueError('invalid initialization')
        state=LocalState(node,value,{node:value},value,0)
        state.output_value=self.output(state)
        return state

    def message(self,state):
        """Immutable, serialization-friendly transmission of known input witnesses."""
        return tuple(sorted(state.view.items()))

    def transition(self,state,received_messages):
        updated=dict(state.view)
        for message in received_messages:
            for node,value in message:
                if not 0<=node<self.graph.n or value not in self.alphabet:
                    raise ValueError('invalid message')
                if node in updated and updated[node]!=value:
                    raise ValueError('conflicting witness for immutable input')
                updated[node]=value
        new=LocalState(state.node,state.own_input,updated,state.output_value,state.round+1)
        new.output_value=self.output(new)
        return new

    def output(self,state):
        safe=self.certificate.evaluate(state.view)['safe']
        return safe[0] if safe else min(state.view.values())

    def full_decision(self,inputs):return self.certificate.full_decision(inputs)
    def evaluate(self,view):return self.certificate.evaluate(view)

    def specification(self):
        return {'machine':'finite-certificate-local-view','kind':self.kind,
                'n':self.graph.n,'alphabet':self.alphabet,
                'graph':self.graph.to_dict(),
                'parameters':self.certificate.params,
                'validation':self.validation}


def compile_protocol(graph,alphabet,config,validate_cases=4096):
    cert,validation=compile_certificate(graph,alphabet,config,validate_cases)
    return CompiledProtocol(cert,validation)
