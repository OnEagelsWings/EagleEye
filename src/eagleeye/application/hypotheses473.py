"""Competing, explicitly provisional explanations backed by exact source quotes."""
from typing import Annotated
from pydantic import Field, model_validator
from .assistant471 import StrictModel, Citation
from .question472 import Answer472

class Alternative473(StrictModel):
    title: Annotated[str, Field(min_length=5, max_length=160)]
    explanation: Annotated[str, Field(min_length=12, max_length=2000)]
    supporting: Annotated[list[Citation], Field(max_length=5)]
    contradicting: Annotated[list[Citation], Field(max_length=5)]
    missing_evidence: Annotated[str, Field(min_length=12, max_length=1000)]
    verification_question: Annotated[str, Field(min_length=8, max_length=1000)]

    @model_validator(mode='after')
    def anchored(self):
        if not self.supporting and not self.contradicting:
            raise ValueError('Each alternative requires at least one source citation')
        overlap={' '.join(c.quote.split()) for c in self.supporting} & {' '.join(c.quote.split()) for c in self.contradicting}
        if overlap:
            raise ValueError('The same exact quotation must not count as both supporting and contradicting one alternative')
        return self

class Analysis473(Answer472):
    alternatives: Annotated[list[Alternative473], Field(max_length=3)]

    @model_validator(mode='after')
    def competing(self):
        if self.answer_status=='insufficient_evidence':
            if self.alternatives:
                raise ValueError('Abstentions cannot carry model-generated alternatives')
        elif len(self.alternatives)<2 or len({a.title.strip().casefold() for a in self.alternatives})!=len(self.alternatives):
            raise ValueError('At least two distinctly named alternatives are required')
        return self
