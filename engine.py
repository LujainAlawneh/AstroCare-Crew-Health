"""AstroCare deterministic, offline, non-clinical rule evaluator.
No source narrative is compiled into executable rules. Clinical mode is hard disabled.
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum

CLINICAL_MODE_ENABLED = False
class Truth(str, Enum):
    TRUE='true'; FALSE='false'; UNKNOWN='unknown'

def truth(value):
    if value is True or value == 'true': return Truth.TRUE
    if value is False or value == 'false': return Truth.FALSE
    return Truth.UNKNOWN

def evaluate(expr, facts):
    """Evaluate declarative expressions. Return result plus missing fact IDs."""
    op=expr.get('op')
    if op=='fact':
        key=expr['id']; v=truth(facts.get(key)); return v, ([key] if v==Truth.UNKNOWN else [])
    if op=='not':
        v,m=evaluate(expr['arg'],facts)
        return ({Truth.TRUE:Truth.FALSE,Truth.FALSE:Truth.TRUE,Truth.UNKNOWN:Truth.UNKNOWN}[v],m)
    if op not in ('and','or'): raise ValueError('Unsupported operator: '+str(op))
    children=[evaluate(a,facts) for a in expr['args']]
    vals=[v for v,_ in children]
    result=(Truth.FALSE if Truth.FALSE in vals else Truth.UNKNOWN if Truth.UNKNOWN in vals else Truth.TRUE) if op=='and' else (Truth.TRUE if Truth.TRUE in vals else Truth.UNKNOWN if Truth.UNKNOWN in vals else Truth.FALSE)
    missing=list(dict.fromkeys(k for _,keys in children for k in keys))
    return result, missing

def validate_measurements(measurements, freshness_policy):
    """Freshness limits are mandatory per measurement; never assume one."""
    issues=[]; validated={}
    for m in measurements:
        key=m.get('id','unknown')
        if not all(k in m for k in ('value','unit','timestamp','context')):
            issues.append({'id':key,'issue':'missing value/unit/timestamp/context'}); continue
        try:
            stamp=datetime.fromisoformat(m['timestamp'].replace('Z','+00:00'))
            if stamp.tzinfo is None: raise ValueError('timezone missing')
        except (ValueError,AttributeError):
            issues.append({'id':key,'issue':'invalid timestamp or missing timezone'}); continue
        policy=freshness_policy.get(key)
        if not policy or policy.get('approved') is not True or not isinstance(policy.get('max_age_seconds'),(int,float)):
            issues.append({'id':key,'issue':'no approved freshness policy'});continue
        age=(datetime.now(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds()
        if age<0 or age>policy['max_age_seconds']:
            issues.append({'id':key,'issue':'timestamp outside approved freshness policy'});continue
        if m['unit'] != policy.get('unit'):
            issues.append({'id':key,'issue':'unit differs from approved policy'});continue
        validated[key]=m
    return validated,issues

def assess(facts, rules, clinical=False):
    if clinical or CLINICAL_MODE_ENABLED: raise PermissionError('Clinical operation disabled pending validation and authorization')
    if not isinstance(facts,dict): raise TypeError('facts must be a dict')
    results=[]; unknown_red_flags=[]
    for rule in rules:
        if rule.get('approval_status') not in ('demo_only','approved') or not rule.get('source_ids') or not rule.get('version'):
            continue
        # approved is still demo-only until clinical mode is authorized in a future reviewed build
        v,missing=evaluate(rule['expression'],facts)
        item={'rule_id':rule['id'],'kind':rule['kind'],'candidate_id':rule.get('candidate_id'), 'result':v.value,'missing':missing,'source_ids':rule['source_ids'],'version':rule['version'],'next_step':rule.get('next_step','Review with medical officer'), 'matched_features':[f for f in rule.get('feature_ids',[]) if truth(facts.get(f))==Truth.TRUE], 'conflicts': [f for f in rule.get('feature_ids',[]) if truth(facts.get(f))==Truth.FALSE]}
        results.append(item)
        if rule['kind'] in ('emergency','urgent') and v==Truth.UNKNOWN:unknown_red_flags.append(item)
    emergencies=[r for r in results if r['kind']=='emergency' and r['result']=='true']
    urgent=[r for r in results if r['kind']=='urgent' and r['result']=='true']
    candidates=[r for r in results if r['kind']=='candidate' and r['result']=='true']
    unresolved=[r for r in results if r['kind']=='candidate' and r['result']=='unknown']
    level='emergency' if emergencies else 'urgent_review' if urgent else 'unresolved'
    return {'mode':'SYNTHETIC DEMO — NOT CLINICAL', 'risk_workflow':level,'matched_emergency_rules':emergencies,'matched_urgent_rules':urgent,'unknown_red_flags':unknown_red_flags,'candidate_patterns':candidates,'unresolved_patterns':unresolved,'all_evaluations':results,'status':'Unresolved — further assessment required' if not candidates else 'Candidate patterns require clinician review', 'clinical_mode_enabled':False}
