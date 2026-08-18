from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'src'
SERVICE=ROOT.parents[1]/'services'/'studio-nexmind-p8'
sys.path.insert(0,str(SRC));sys.path.insert(0,str(SERVICE))

from nexmind_god_mode.art_contracts import validate_art_output
from nexmind_god_mode.art_director import ArtDirector
from nexmind_god_mode.p3_producer import P3ExecutiveProducer
from nexmind_god_mode.showrunner_p8 import NexMindSupremeShowrunnerP8
from nexmind_god_mode.contracts import ContractViolation
import orchestrator as o


def story():
    return {
        'film_thesis':{
            'central_argument':'One precise change protects a delicate result and human attention.',
            'film_kind':'commercial','audience_before':'control feels technical','audience_after':'control feels useful',
            'hero_kind':'delicate food result','camera_idea':'hold one causal tabletop geography',
            'emotional_trajectory':['tension','relief'],'visual_trajectory':['threat','control','payoff'],
            'opening_contract':'show imminent failure','final_payoff':'preserved result reaches person','anti_goals':['no feature list']},
        'beats':[
            {'beat_id':'B1','purpose':'threat','question':'what is at risk','audience_before':'neutral','audience_after':'sees risk','hero_state':'seam threatened','reveal':'active boil threatens seam','required_claim_ids':['C1']},
            {'beat_id':'B2','purpose':'payoff','question':'what changes','audience_before':'sees risk','audience_after':'sees control','hero_state':'seam intact','reveal':'steady simmer preserves seam','required_claim_ids':['C1']},
        ]}


def visual():
    return {'candidate_id':'V1','representation':'LIVE_ACTION','visual_thesis':'food state proves useful control','hero_kind':'wonton seam','transformation':'threatened to preserved','camera_idea':'tabletop causal geography','rationale':'physical proof','concept_signature':{},'rehearsal_states':[], 'originality_guard':{},
            'beat_treatments':[{'beat_id':'B1','hero_state':'threat','visual_action':'boil threatens seam','audience_takeaway':'risk'},{'beat_id':'B2','hero_state':'preserved','visual_action':'simmer holds seam','audience_takeaway':'control'}]}


def art_candidate(cid='A1'):
    return {
        'candidate_id':cid,'visual_candidate_id':'V1','art_thesis':'Practical tabletop proof with the seam dominant.',
        'hero':{'semantic_ref':'same wonton seam','art_budget':'HIGH','prominence':'DOMINANT','recognizable_required':True},
        'composition':{'archetype':'proof tabletop','hierarchy_order':['seam','broth','hands'],'negative_space_intent':'quiet proof zone','density':'BALANCED','asymmetry_intent':'pot weighted left','support_budget':7,'decoration_budget':4},
        'form_request':{'concept':'practical live action food proof','representation':'LIVE_ACTION','semantic_parts':['wonton','broth','hands'],'required_operations':['preserve continuity'],'style':'naturalistic'},
        'beat_art':[
            {'beat_id':'B1','settled_visual_state':'same seam visibly threatened but intact','focal_owner':'seam','supporting_roles':['broth','pot','hand','spoon','table','learner','cooktop'],'meaning_without_motion':True},
            {'beat_id':'B2','settled_visual_state':'same seam preserved in active steady simmer','focal_owner':'seam','supporting_roles':['broth','pot','hand','spoon','table','learner','cooktop'],'meaning_without_motion':True},
        ],
        'typography_intent':'none','risk_notes':[]}


class OneReplyProvider:
    def __init__(self,payload): self.payload=copy.deepcopy(payload); self.requests=[]
    def complete(self,task,request): self.requests.append((task,copy.deepcopy(request))); return copy.deepcopy(self.payload)


class RepairGovernanceV4Tests(unittest.TestCase):
    def test_art_contract_allows_one_candidate_only_in_surgical_repair(self):
        payload={'candidates':[art_candidate()]}
        with self.assertRaises(ContractViolation): validate_art_output(payload,{'B1','B2'},'V1')
        out=validate_art_output(payload,{'B1','B2'},'V1',repair_mode=True)
        self.assertEqual(1,len(out))

    def test_art_director_uses_exact_anchor_for_surgical_repair(self):
        candidate=art_candidate('A-REPAIRED')
        provider=OneReplyProvider({'candidates':[candidate]})
        brief={'autonomous_revision_context':{'department':'ART_DIRECTION','previous_output':art_candidate('A-OLD'),'sticky_requirements':['cover every beat']}}
        out=ArtDirector(provider).propose('P',brief,story(),visual(),{}, {})
        self.assertEqual(1,len(out))
        req=provider.requests[0][1]
        self.assertEqual('A-OLD',req['repair_anchor']['candidate_id'])
        self.assertIn('exactly one',req['instruction']['goal'])

    def test_art_producer_has_no_fixed_support_or_decoration_count_reject(self):
        provider=OneReplyProvider({'verdict':'ACCEPT','issues':[],'strengths':['clear hierarchy'],'revision_brief':'','commercial_confidence':'HIGH'})
        review=P3ExecutiveProducer(provider).review_art('P',{'topic':'x'},story(),visual(),art_candidate(),{'status':'SUPPORTED'})
        self.assertEqual('ACCEPT',review['verdict'])
        self.assertFalse(any((x.get('code') in {'SUPPORT_OVERLOAD','DECORATION_OVERLOAD'}) for x in review.get('issues',[]) if isinstance(x,dict)))

    def test_art_empirical_test_demand_is_deferred(self):
        provider=OneReplyProvider({'verdict':'REVISE','issues':[{'severity':'MAJOR','issue':'No real food-and-camera test result is supplied.','required_change':'Run a practical food-and-camera test and provide measured timing.'}], 'strengths':['strong frame'],'revision_brief':'Run the test.','commercial_confidence':'HIGH'})
        review=P3ExecutiveProducer(provider).review_art('P',{'topic':'x'},story(),visual(),art_candidate(),{'status':'SUPPORTED'})
        self.assertEqual('ACCEPT',review['verdict'])
        self.assertEqual([],review['issues'])
        self.assertEqual(1,len(review.get('deferred_production_validations') or []))

    def test_contract_miss_does_not_consume_final_creative_attempt(self):
        sr=NexMindSupremeShowrunnerP8('P',{'topic':'x'})
        o._ensure_repair_state(sr,{'STORY':2,'VISUAL_CONCEPT':3,'ART_DIRECTION':3,'CINEMATOGRAPHY':2,'EDITORIAL_RHYTHM':2,'MOTION_PERFORMANCE':3,'SOUND_DIRECTION':2})
        sr.state['autonomous_creative_repair']['attempts']['ART_DIRECTION']=3
        sr.state['brief']['autonomous_revision_context']={'department':'ART_DIRECTION','previous_output':art_candidate('ANCHOR')}
        o._schedule_director_contract_repair(sr,'ART_DIRECTION',ContractViolation('beat_art must cover every beat'))
        self.assertEqual(2,sr.state['autonomous_creative_repair']['attempts']['ART_DIRECTION'])
        self.assertEqual(1,sr.state['autonomous_creative_repair']['contract_repairs']['ART_DIRECTION'])
        self.assertEqual('ANCHOR',sr.state['brief']['autonomous_revision_context']['previous_output']['candidate_id'])

    def test_art_budget_exhaustion_opens_new_art_lineage_not_visual(self):
        sr=NexMindSupremeShowrunnerP8('P',{'topic':'x'})
        o._ensure_repair_state(sr,{'STORY':2,'VISUAL_CONCEPT':3,'ART_DIRECTION':3,'CINEMATOGRAPHY':2,'EDITORIAL_RHYTHM':2,'MOTION_PERFORMANCE':3,'SOUND_DIRECTION':2})
        sr.state['autonomous_creative_repair']['attempts'].update({'STORY':2,'VISUAL_CONCEPT':2,'ART_DIRECTION':3})
        sr.state['decisions']['film_thesis']={'proposal_id':'S','payload':{'story':story()},'department':'StoryDirector'}
        sr.state['decisions']['visual_concept']={'proposal_id':'V','payload':copy.deepcopy(visual()),'department':'VisualConceptDirector'}
        sr.state['decisions']['art_direction']={'proposal_id':'A','payload':copy.deepcopy(art_candidate('A-OLD')),'department':'ArtDirector'}
        err=o.CreativeRepairBudgetExhausted('ART_DIRECTION',3,3,reason='No Producer-accepted Art Direction candidate',context={'issues':[{'severity':'MAJOR','issue':'art route exhausted','required_change':'materially rethink art realization'}]})
        owner,chain=o._resolve_available_escalation_owner(sr,'ART_DIRECTION')
        self.assertEqual('ART_DIRECTION',owner)
        self.assertEqual(['ART_DIRECTION'],chain)
        rr={'issues':copy.deepcopy(err.context['issues']),'revision_plan':['rethink'], 'round':1}
        ctx=o._apply_in_place_broader_replan(sr,owner=owner,source_error=err,repair_request=rr)
        self.assertIn('film_thesis',sr.state['decisions'])
        self.assertIn('visual_concept',sr.state['decisions'])
        self.assertNotIn('art_direction',sr.state['decisions'])
        self.assertEqual('MATERIAL_STRATEGY_REPLAN',ctx['repair_mode'])
        self.assertIsNone(ctx['previous_output'])
        self.assertEqual(0,sr.state['autonomous_creative_repair']['attempts']['ART_DIRECTION'])
        self.assertEqual(2,sr.state['autonomous_creative_repair']['attempts']['VISUAL_CONCEPT'])

    def test_visual_budget_exhaustion_never_escalates_to_story_by_budget_alone(self):
        sr=NexMindSupremeShowrunnerP8('P',{'topic':'x'})
        o._ensure_repair_state(sr,{'STORY':2,'VISUAL_CONCEPT':3,'ART_DIRECTION':3,'CINEMATOGRAPHY':2,'EDITORIAL_RHYTHM':2,'MOTION_PERFORMANCE':3,'SOUND_DIRECTION':2})
        sr.state['autonomous_creative_repair']['attempts'].update({'STORY':2,'VISUAL_CONCEPT':3,'ART_DIRECTION':3})
        owner,chain=o._resolve_available_escalation_owner(sr,'VISUAL_CONCEPT')
        self.assertEqual('VISUAL_CONCEPT',owner)
        self.assertEqual(['VISUAL_CONCEPT'],chain)


if __name__=='__main__': unittest.main(verbosity=2)
