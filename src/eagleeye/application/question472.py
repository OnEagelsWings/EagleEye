"""Structured source-bound question answers with an explicit abstention state."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from .assistant471 import StrictModel, Statement

class Answer472(StrictModel):
    answer_status: Literal['source_bound', 'insufficient_evidence']
    statements: Annotated[list[Statement], Field(max_length=12)]
    uncertainties: Annotated[list[Annotated[str, Field(min_length=1, max_length=1000)]], Field(min_length=1, max_length=8)]

    @model_validator(mode='after')
    def bounded_answer(self):
        if self.answer_status == 'source_bound' and not self.statements:
            raise ValueError('A source-bound answer requires cited statements')
        if self.answer_status == 'insufficient_evidence' and self.statements:
            raise ValueError('An abstention must not contain factual statements')
        return self
