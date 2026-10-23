"""Human item-level review of untrusted model output, with no fact promotion."""
from typing import Annotated, Literal
from pydantic import Field
from .assistant471 import StrictModel

class StaleDraftError(ValueError):
    pass

class Assessment474(StrictModel):
    verdict: Literal['supported', 'contradicted', 'unclear']
    note: Annotated[str, Field(min_length=12, max_length=1000)]


def review_items(run):
    items=[{'item_id':f's{i}','text':item['text']} for i,item in enumerate(run['summary']['statements'])]
    for i,item in enumerate(run['summary'].get('alternatives',[])):
        items.append({'item_id':f'h{i}','text':' · '.join(item[k] for k in ['title','explanation','missing_evidence','verification_question'])})
    items.extend({'item_id':f'u{i}','text':text} for i,text in enumerate(run['summary']['uncertainties']))
    return items


def validate_assessments(run, assessments):
    expected={item['item_id'] for item in review_items(run)}
    if not isinstance(assessments,dict) or set(assessments)!=expected:
        raise ValueError('Jede Aussage, Hypothese und Modellnotiz einzeln prüfen.')
    result={}
    for item_id,value in assessments.items():
        assessed=Assessment474.model_validate(value)
        if len(assessed.note.strip())<12:
            raise ValueError('Eine inhaltliche Begründung ist erforderlich.')
        result[item_id]={'verdict':assessed.verdict,'note':assessed.note.strip()}
    return result
