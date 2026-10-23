"""Structured source-bound answers; abstentions contain only constrained gap codes."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from .assistant471 import StrictModel, Statement

GapReason = Literal['not_in_selected_excerpts', 'conflicting_sources', 'source_quality_unclear', 'question_outside_scope']
GAP_LABELS = {
    'not_in_selected_excerpts': 'Die ausgewählten Auszüge reichen für die Arbeitsfrage nicht aus.',
    'conflicting_sources': 'Widersprüche in der Quellenauswahl müssen menschlich geprüft werden.',
    'source_quality_unclear': 'Die Qualität der ausgewählten Quellen ist noch ungeklärt.',
    'question_outside_scope': 'Die Arbeitsfrage liegt außerhalb der ausgewählten Beleggrundlage.',
}

class Answer472(StrictModel):
    answer_status: Literal['source_bound', 'insufficient_evidence']
    statements: Annotated[list[Statement], Field(max_length=12)]
    uncertainties: Annotated[list[Annotated[str, Field(min_length=1, max_length=1000)]], Field(max_length=8)]
    gap_reasons: Annotated[list[GapReason], Field(max_length=4)] = Field(default_factory=list)

    @model_validator(mode='after')
    def bounded_answer(self):
        if self.answer_status == 'source_bound':
            if not self.statements or not self.uncertainties or self.gap_reasons:
                raise ValueError('A source-bound answer requires cited statements and uncertainty notes')
        elif self.statements or self.uncertainties or not self.gap_reasons:
            raise ValueError('An abstention permits only constrained gap reason codes, no model prose')
        return self
