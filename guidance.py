"""Offline educational evidence matching over the supplied research workbook.
This does not enable clinical mode, diagnose disease, or calculate disease probabilities.
"""
import json
from pathlib import Path
ROOT=Path(__file__).parent
KB=json.loads((ROOT/'data/source_knowledge_base.json').read_text(encoding='utf-8'))
REF=json.loads((ROOT/'data/guidance_reference.json').read_text(encoding='utf-8'))
SOURCES={s['id']:s for s in REF['sources']}

def state(value):
    if value is True or value in ('true','yes','Yes'):return 'yes'
    if value is False or value in ('false','no','No'):return 'no'
    return 'unknown'

def clean_confirmations(raw, allowed):
    if raw is None:return {}
    if not isinstance(raw,dict) or len(raw)>300:raise ValueError('Invalid confirmation map')
    out={}
    for key,v in raw.items():
        if key not in allowed or v not in ('yes','no','unknown'):raise ValueError('Invalid confirmation')
        out[key]=v
    return out

def educational_guidance(module, answers, confirmations=None, alert_answers=None):
    candidates=[c for c in KB['candidates'] if c['module']==module]
    alerts=[a for a in KB['alerts'] if a['module']==module]
    feature_keys={f"{c['id']}:{i}" for c in candidates for i,_ in enumerate(c['supporting_features'].splitlines())}
    confirm=clean_confirmations(confirmations,feature_keys)
    warning_answers=clean_confirmations(alert_answers,{a['id'] for a in alerts})
    c_refs={c['id']:c for c in REF['candidates']};a_refs={a['id']:a for a in REF['alerts']}
    question_ids={q['id'] for q in KB['questions'] if q['module']==module}
    answers=answers if isinstance(answers,dict) else {}
    # Existing grouped answers can hint at an association, but cannot establish a
    # complete source feature. The reader must confirm the exact feature text.
    hints={}
    for rule in KB['pilot_rules']:
        if rule['question_id'] not in question_ids:continue
        answer=answers.get(rule['question_id'])
        token=rule['expected_token'].lower()
        matched=token=='yes' and state(answer)=='yes'
        if isinstance(answer,dict):
            values=list(answer.get('fields',{}).values()) if isinstance(answer.get('fields',{}),dict) else []
            matched=any(str(v).strip().lower()==token for v in values)
        elif isinstance(answer,str) and token!='yes':matched=answer.strip().lower()==token
        if matched:hints.setdefault(rule['candidate_id'],[]).append({'question_id':rule['question_id'],'text':rule['evidence'],'scope':'Grouped/or draft association only; exact source feature needs confirmation'})
    # Precise user-selected pain character gives a useful non-diagnostic hint.
    head=answers.get('M01_Q02',{})
    if isinstance(head,dict):
        fields=head.get('fields',{})
        if fields.get('1')=='Throbbing / pulsating':hints.setdefault('M01_C01',[]).append({'question_id':'M01_Q02','text':'Throbbing / pulsating pain selected','scope':'Reported pain character; other features and alternative causes remain unresolved'})
        if fields.get('1')=='Pressure / tightness':hints.setdefault('M01_C02',[]).append({'question_id':'M01_Q02','text':'Pressure / tightness selected','scope':'Laterality and other causes have not been established'})
    patterns=[]
    for c in candidates:
        features=[{'id':f"{c['id']}:{i}",'text':text,'state':confirm.get(f"{c['id']}:{i}",'unknown')} for i,text in enumerate(c['supporting_features'].splitlines()) if text.strip()]
        yes=sum(f['state']=='yes' for f in features);no=sum(f['state']=='no' for f in features);unknown=len(features)-yes-no
        patterns.append({**c,'features':features,'confirmed_features':yes,'not_reported_features':no,'unknown_features':unknown,'answer_associations':hints.get(c['id'],[]),'source_ids':c_refs.get(c['id'],{}).get('source_ids',[]),'match_label':'Mixed reported features — review differences' if yes and no else 'Reported feature support' if yes else 'Listed features not reported — not ruled out' if no else 'Answer association — clarify details' if hints.get(c['id']) else 'Not yet established','ranking_note':'Sorted by reported feature support, not medical likelihood'})
    patterns.sort(key=lambda c:(-c['confirmed_features'],-len(c['answer_associations']),c['id']))
    # Narrow, explicit warning-answer links. Grouped/ambiguous answers elsewhere
    # remain unknown and require confirmation of the exact source description.
    warning_links={'M01_A01':['M01_Q04','M01_Q06'],'M03_A01':['M03_Q06']}
    warnings=[]
    for a in alerts:
        linked=[q for q in warning_links.get(a['id'],[]) if state(answers.get(q))=='yes']
        warnings.append({**a,'state':'yes' if linked else warning_answers.get(a['id'],'unknown'),'source_ids':a_refs.get(a['id'],{}).get('source_ids',[]),'reported_in_questions':linked,'origin':'existing_question_answer' if linked else 'source_description_confirmation'})
    active=[w for w in warnings if w['state']=='yes'];unknown_warnings=[w for w in warnings if w['state']=='unknown']
    level='emergency' if any(w['category']=='Emergency' for w in active) else 'urgent' if active else 'incomplete' if unknown_warnings else 'review'
    # Never suggest self-care when a reported emergency warning is active.
    supported={c['id'] for c in patterns if c['confirmed_features'] or c['answer_associations']}
    care=[dict(c) for c in REF['care_options'] if c['module']==module and (not c['candidate_ids'] or bool(supported.intersection(c['candidate_ids'])))]
    non_drug=[c for c in care if c['type']=='Non-drug measure']
    clinician_only=[c for c in care if c['type']!='Non-drug measure']
    if level in ('emergency','urgent','incomplete'):non_drug=[];clinician_only=[]
    refs=set()
    for item in patterns+warnings+care:refs.update(item.get('source_ids',[]))
    def answered(value):
        if isinstance(value,dict):return any(str(v).lower() not in ('','not sure','unknown','unspecified') for v in value.get('fields',{}).values()) or bool(str(value.get('notes','')).strip())
        return value not in (None,'','unknown','Not sure','Unspecified')
    count=sum(answered(answers.get(q)) for q in question_ids)
    return {'module':module,'module_name':next((m['name'] for m in KB['modules'] if m['id']==module),'Health check'),'purpose':'Educational symptom-feature matching; not a diagnosis or disease probability','patterns':patterns,'warnings':warnings,'safety':{'level':level,'reported_warnings':len(active),'unanswered_warnings':len(unknown_warnings),'statement':'No warning reported is not medical clearance.'},'non_drug_options':non_drug,'clinician_only_options':clinician_only,'sources':[SOURCES[x] for x in sorted(refs) if x in SOURCES],'questions_answered':count,'questions_total':len(question_ids),'follow_up':next((f for f in REF.get('follow_up',[]) if f['module']==module),None),'confirmations':confirm,'alert_answers':warning_answers,'source_provenance':REF['provenance'],'clinical_validation':REF['clinical_validation']}
