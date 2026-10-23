from html import escape
from eagleeye.application.review474 import review_items


def render_review_matrix(run):
    result='<fieldset><legend>Jeden KI-Inhalt am Original prüfen</legend><p>Für eine Prüfbestätigung benötigt jede Aussage, Hypothese und Modellnotiz ein Urteil und eine eigene Begründung. Verwerfen ist auch ohne Einzelprüfung möglich.</p>'
    for item in review_items(run):
        key=item['item_id']
        result+='<label>'+escape(item['text'])+'<select name="verdict_'+key+'"><option value="">Noch nicht geprüft</option><option value="supported">Durch Auswahl gestützt</option><option value="contradicted">Durch Auswahl widersprochen</option><option value="unclear">Unklar / weitere Belege nötig</option></select></label><label>Begründung <textarea name="item_note_'+key+'" maxlength="1000" rows="2"></textarea></label>'
    return result+'</fieldset>'


def read_assessments(form):
    return {key[8:]:{'verdict':str(value),'note':str(form.get('item_note_'+key[8:],''))}
            for key,value in form.items() if key.startswith('verdict_')}


def render_assessment_history(run):
    labels={item['item_id']:item['text'] for item in review_items(run)}
    result=''
    for item_id,assessment in (run['review'].get('assessments') or {}).items():
        verdict={'supported':'Gestützt','contradicted':'Widersprochen','unclear':'Unklar'}[assessment['verdict']]
        result+='<p><strong>'+escape(labels[item_id])+'</strong> · '+escape(verdict)+': '+escape(assessment['note'])+'</p>'
    return result
