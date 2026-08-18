from __future__ import annotations

# JSON Schemas supplied to providers for strict structured output.
# Runtime validators remain authoritative even when a provider claims schema compliance.


SOURCE_VISUAL_UNDERSTANDING_SCHEMA = {
    "type":"object","additionalProperties":False,
    "required":["summary","observations","unresolved_visuals","source_integrity"],
    "properties":{
        "summary":{"type":"string"},
        "observations":{"type":"array","maxItems":80,"items":{
            "type":"object","additionalProperties":False,
            "required":["source_id","locator","sha256","observation","factual_claims","confidence"],
            "properties":{
                "source_id":{"type":"string"},"locator":{"type":"string"},"sha256":{"type":"string"},
                "observation":{"type":"string"},
                "factual_claims":{"type":"array","maxItems":12,"items":{"type":"string"}},
                "confidence":{"type":"string","enum":["LOW","MEDIUM","HIGH"]},
            },
        }},
        "unresolved_visuals":{"type":"array","maxItems":80,"items":{
            "type":"object","additionalProperties":False,
            "required":["source_id","locator","reason"],
            "properties":{"source_id":{"type":"string"},"locator":{"type":"string"},"reason":{"type":"string"}},
        }},
        "source_integrity":{"type":"object","additionalProperties":False,
            "required":["used_only_provided_visuals","invented_facts"],
            "properties":{"used_only_provided_visuals":{"type":"boolean"},"invented_facts":{"type":"boolean"}},
        },
    },
}

SOURCE_UNDERSTANDING_SCHEMA = {
    "type":"object","additionalProperties":False,
    "required":["summary","claims","contradictions","unresolved_questions","creative_relevance","visual_evidence_needs","source_integrity"],
    "properties":{
        "summary":{"type":"string"},
        "claims":{"type":"array","maxItems":80,"items":{
            "type":"object","additionalProperties":False,
            "required":["claim","source_claim_ids","confidence","relevance"],
            "properties":{
                "claim":{"type":"string"},
                "source_claim_ids":{"type":"array","minItems":1,"maxItems":12,"items":{"type":"string"}},
                "confidence":{"type":"string","enum":["LOW","MEDIUM","HIGH"]},
                "relevance":{"type":"string"},
            },
        }},
        "contradictions":{"type":"array","maxItems":40,"items":{
            "type":"object","additionalProperties":False,
            "required":["issue","source_claim_ids","handling"],
            "properties":{
                "issue":{"type":"string"},
                "source_claim_ids":{"type":"array","minItems":2,"maxItems":12,"items":{"type":"string"}},
                "handling":{"type":"string","enum":["PRESERVE_CONFLICT","REQUEST_CLARIFICATION_IF_CRITICAL","USE_ONLY_NON_CONFLICTING_FACTS"]},
            },
        }},
        "unresolved_questions":{"type":"array","maxItems":40,"items":{"type":"string"}},
        "creative_relevance":{"type":"array","maxItems":40,"items":{"type":"string"}},
        "visual_evidence_needs":{"type":"array","maxItems":40,"items":{
            "type":"object","additionalProperties":False,
            "required":["source_id","page","reason"],
            "properties":{"source_id":{"type":"string"},"page":{"type":"integer","minimum":1},"reason":{"type":"string"}},
        }},
        "source_integrity":{"type":"object","additionalProperties":False,
            "required":["used_only_provided_evidence","contradictions_preserved","invented_facts"],
            "properties":{
                "used_only_provided_evidence":{"type":"boolean"},
                "contradictions_preserved":{"type":"boolean"},
                "invented_facts":{"type":"boolean"},
            },
        },
    },
}

STORY_SCHEMA = {
    "type":"object",
    "additionalProperties":False,
    "required":["film_thesis","beats"],
    "properties":{
        "film_thesis":{
            "type":"object","additionalProperties":False,
            "required":["central_argument","film_kind","audience_before","audience_after","hero_kind","camera_idea","emotional_trajectory","visual_trajectory","opening_contract","final_payoff","anti_goals"],
            "properties":{
                "central_argument":{"type":"string"},
                "film_kind":{"type":"string"},
                "audience_before":{"type":"string"},
                "audience_after":{"type":"string"},
                "hero_kind":{"type":"string"},
                "camera_idea":{"type":"string"},
                "emotional_trajectory":{"type":"array","items":{"type":"string"},"minItems":2},
                "visual_trajectory":{"type":"array","items":{"type":"string"},"minItems":2},
                "opening_contract":{"type":"string"},
                "final_payoff":{"type":"string"},
                "anti_goals":{"type":"array","items":{"type":"string"}},
            },
        },
        "beats":{
            "type":"array","minItems":2,
            "items":{
                "type":"object","additionalProperties":False,
                "required":["beat_id","purpose","question","audience_before","audience_after","hero_state","reveal","required_claim_ids","narration_mode","narration_text","narration_purpose"],
                "properties":{
                    "beat_id":{"type":"string"},
                    "purpose":{"type":"string"},
                    "question":{"type":"string"},
                    "audience_before":{"type":"string"},
                    "audience_after":{"type":"string"},
                    "hero_state":{"type":"string"},
                    "reveal":{"type":"string"},
                    "required_claim_ids":{"type":"array","items":{"type":"string"}},
                    "narration_mode":{"type":"string","enum":["VOICEOVER","SILENT"]},
                    "narration_text":{"type":"string"},
                    "narration_purpose":{"type":"string"},
                },
            },
        },
    },
}

VISUAL_SCHEMA = {
    "type":"object","additionalProperties":False,
    "required":["candidates"],
    "properties":{
        "candidates":{
            "type":"array","minItems":1,
            "items":{
                "type":"object","additionalProperties":False,
                "required":["candidate_id","representation","visual_thesis","hero_kind","transformation","camera_idea","rationale","concept_signature","rehearsal_states","originality_guard","beat_treatments"],
                "properties":{
                    "candidate_id":{"type":"string"},
                    "representation":{"type":"string","minLength":1},
                    "visual_thesis":{"type":"string"},
                    "hero_kind":{"type":"string"},
                    "transformation":{"type":"string"},
                    "camera_idea":{"type":"string"},
                    "rationale":{"type":"string"},
                    "concept_signature":{"type":"object","additionalProperties":False,"required":["brief_specific_hook","governing_visual_logic","emotional_engine","memorability_device","transplant_test"],"properties":{
                        "brief_specific_hook":{"type":"string"},"governing_visual_logic":{"type":"string"},"emotional_engine":{"type":"string"},"memorability_device":{"type":"string"},"transplant_test":{"type":"string"}}},
                    "rehearsal_states":{"type":"array","minItems":2,"items":{"type":"object","additionalProperties":False,"required":["label","state","purpose"],"properties":{
                        "label":{"type":"string","minLength":1},"state":{"type":"string","minLength":1},"purpose":{"type":"string","minLength":1}}}},
                    "originality_guard":{"type":"object","additionalProperties":False,"required":["reference_independence","template_risk","why_not_obvious"],"properties":{
                        "reference_independence":{"type":"string"},"template_risk":{"type":"string"},"why_not_obvious":{"type":"string"}}},
                    "beat_treatments":{"type":"array","minItems":1,"items":{
                        "type":"object","additionalProperties":False,
                        "required":["beat_id","hero_state","visual_action","audience_takeaway","supporting_elements","world_state","visual_consequence","continuity_handoff"],
                        "properties":{
                            "beat_id":{"type":"string"},"hero_state":{"type":"string"},"visual_action":{"type":"string"},"audience_takeaway":{"type":"string"},
                            "supporting_elements":{"type":"array","items":{"type":"string"}},"world_state":{"type":"string"},"visual_consequence":{"type":"string"},"continuity_handoff":{"type":"string"}
                        }
                    }},
                },
            },
        }
    }
}

PRODUCER_SCHEMA = {
    "type":"object","additionalProperties":False,
    "required":["verdict","issues","strengths","revision_brief","commercial_confidence"],
    "properties":{
        "verdict":{"type":"string","enum":["ACCEPT","REVISE","REJECT"]},
        "issues":{"type":"array","items":{"type":"object","required":["blocking"],"properties":{"blocking":{"type":"boolean"}},"additionalProperties":True}},
        "strengths":{"type":"array","items":{"type":"string"}},
        "revision_brief":{"type":"string"},
        "commercial_confidence":{"type":"string","enum":["LOW","MEDIUM","HIGH"]},
        "notes":{"type":"string"}
    }
}

ART_SCHEMA = {
    "type":"object","additionalProperties":False,"required":["candidates"],
    "properties":{"candidates":{"type":"array","minItems":2,"items":{
        "type":"object","additionalProperties":False,
        "required":["candidate_id","art_thesis","art_bible","hero","composition","form_request","beat_art","typography_intent","risk_notes"],
        "properties":{
            "candidate_id":{"type":"string"},"art_thesis":{"type":"string"},
            "art_bible":{"type":"object","additionalProperties":False,"required":["shape_language","line_edge_language","palette_relationship","material_texture_language","lighting_value_structure","depth_language","environment_language","prop_language","character_language","typography_relationship","continuity_rules"],"properties":{
                "shape_language":{"type":"string"},"line_edge_language":{"type":"string"},"palette_relationship":{"type":"string"},"material_texture_language":{"type":"string"},"lighting_value_structure":{"type":"string"},"depth_language":{"type":"string"},"environment_language":{"type":"string"},"prop_language":{"type":"string"},"character_language":{"type":"string"},"typography_relationship":{"type":"string"},"continuity_rules":{"type":"array","minItems":2,"items":{"type":"string"}}}},
            "hero":{"type":"object","additionalProperties":False,"required":["semantic_ref","art_budget","prominence","recognizable_required"],"properties":{
                "semantic_ref":{"type":"string"},"art_budget":{"type":"string","enum":["HIGH","MEDIUM","LOW"]},"prominence":{"type":"string","enum":["DOMINANT","PRIMARY","SECONDARY"]},"recognizable_required":{"type":"boolean"}}},
            "composition":{"type":"object","additionalProperties":False,"required":["archetype","hierarchy_order","negative_space_intent","density","asymmetry_intent","foreground_strategy","midground_strategy","background_strategy","scale_contrast_intent","overlap_intent","execution_directives","support_budget","decoration_budget"],"properties":{
                "archetype":{"type":"string"},"hierarchy_order":{"type":"array","items":{"type":"string"},"minItems":1},"negative_space_intent":{"type":"string"},"density":{"type":"string","enum":["SPARSE","BALANCED","RICH"]},"asymmetry_intent":{"type":"string"},"foreground_strategy":{"type":"string"},"midground_strategy":{"type":"string"},"background_strategy":{"type":"string"},"scale_contrast_intent":{"type":"string"},"overlap_intent":{"type":"string"},
                "execution_directives":{"type":"object","additionalProperties":False,"required":["spatial_mode","depth_mode","hero_scale","environment_density","overlap_mode","typography_mode"],"properties":{
                    "spatial_mode":{"type":"string","enum":["FLAT_CANVAS","GROUNDED_SCENE","PRODUCT_STAGE","INFORMATION_SPACE"]},
                    "depth_mode":{"type":"string","enum":["FLAT","LAYERED","DEEP"]},
                    "hero_scale":{"type":"string","enum":["DOMINANT_CLOSE","LARGE","MEDIUM"]},
                    "environment_density":{"type":"string","enum":["MINIMAL","CONTEXTUAL","LIVED_IN"]},
                    "overlap_mode":{"type":"string","enum":["NONE","HERO_SUPPORT","PURPOSEFUL_FOREGROUND"]},
                    "typography_mode":{"type":"string","enum":["EMBEDDED","SUPPORT","HERO"]}
                }},
                "support_budget":{"type":"integer","minimum":0},"decoration_budget":{"type":"integer","minimum":0}}},
            "form_request":{"type":"object","additionalProperties":False,"required":["concept","representation","semantic_parts","required_operations","style"],"properties":{
                "concept":{"type":"string"},"representation":{"type":"string","minLength":1},"semantic_parts":{"type":"array","items":{"type":"string"}},"required_operations":{"type":"array","items":{"type":"string"}},"style":{"type":"string"}}},
            "beat_art":{"type":"array","minItems":2,"items":{"type":"object","additionalProperties":False,"required":["beat_id","settled_visual_state","focal_owner","supporting_roles","environment_state","prop_specificity","character_performance_state","typography_role","depth_read","meaning_without_motion"],"properties":{
                "beat_id":{"type":"string"},"settled_visual_state":{"type":"string"},"focal_owner":{"type":"string"},"supporting_roles":{"type":"array","items":{"type":"string"}},"environment_state":{"type":"string"},"prop_specificity":{"type":"string"},"character_performance_state":{"type":"string"},"typography_role":{"type":"string"},"depth_read":{"type":"string"},"meaning_without_motion":{"type":"boolean"}}}},
            "typography_intent":{"type":"string"},"risk_notes":{"type":"array","items":{"type":"string"}}
        }
    }}}
}

SHOWRUNNER_SELECTION_SCHEMA = {
    "type":"object","additionalProperties":False,
    "required":["selected_candidate_id","why","tradeoffs","rejected_alternatives","decision_basis","brief_specific_evidence","strongest_alternative_id","why_strongest_alternative_loses","selection_risk"],
    "properties":{
        "selected_candidate_id":{"type":"string"},
        "why":{"type":"string"},
        "tradeoffs":{"type":"array","items":{"type":"string"}},
        "rejected_alternatives":{"type":"array","items":{
            "type":"object","additionalProperties":False,
            "required":["candidate_id","reason"],
            "properties":{"candidate_id":{"type":"string"},"reason":{"type":"string"}}
        }},
        "decision_basis":{"type":"object","additionalProperties":False,"required":["brief_specific_fit","creative_distinctiveness","audience_effect","commercial_finish","capability_fit"],"properties":{
            "brief_specific_fit":{"type":"string"},"creative_distinctiveness":{"type":"string"},"audience_effect":{"type":"string"},"commercial_finish":{"type":"string"},"capability_fit":{"type":"string"}}},
        "brief_specific_evidence":{"type":"array","minItems":2,"items":{"type":"string"}},
        "strongest_alternative_id":{"type":"string"},
        "why_strongest_alternative_loses":{"type":"string"},
        "selection_risk":{"type":"string"},
        "notes":{"type":"string"},
    },
}

SCHEMAS={
    "source_visual_understanding": SOURCE_VISUAL_UNDERSTANDING_SCHEMA,
    "source_understanding": SOURCE_UNDERSTANDING_SCHEMA,
    "story": STORY_SCHEMA,
    "visual": VISUAL_SCHEMA,
    "producer": PRODUCER_SCHEMA,
    "showrunner_select": SHOWRUNNER_SELECTION_SCHEMA,
    "art": ART_SCHEMA,
    "art_review": PRODUCER_SCHEMA,
    "showrunner_select_art": SHOWRUNNER_SELECTION_SCHEMA,
    "storyboard_review": PRODUCER_SCHEMA,
}


# P4/P5 exact structured-output schemas. Runtime validators remain authoritative.
CINEMATOGRAPHY_SCHEMA = {'type': 'object',
 'additionalProperties': False,
 'required': ['candidates'],
 'properties': {'candidates': {'type': 'array',
                               'minItems': 3,
                               'maxItems': 5,
                               'items': {'type': 'object',
                                         'additionalProperties': False,
                                         'required': ['candidate_id',
                                                      'cinema_thesis',
                                                      'attention_strategy',
                                                      'shots',
                                                      'global_rules',
                                                      'risk_notes'],
                                         'properties': {'candidate_id': {'type': 'string'},
                                                        'cinema_thesis': {'type': 'string'},
                                                        'attention_strategy': {'type': 'string'},
                                                        'shots': {'type': 'array',
                                                                  'minItems': 2,
                                                                  'items': {'type': 'object',
                                                                            'additionalProperties': False,
                                                                            'required': ['beat_id',
                                                                                         'idiom',
                                                                                         'shot_scale',
                                                                                         'angle',
                                                                                         'subject_target',
                                                                                         'reveal_framing',
                                                                                         'depth_strategy',
                                                                                         'camera_atom',
                                                                                         'transition_relation',
                                                                                         'attention_anchor',
                                                                                         'continuity_reason'],
                                                                            'properties': {'beat_id': {'type': 'string'},
                                                                                           'idiom': {'type': 'string',
                                                                                                     'enum': ['HERO_ESTABLISH',
                                                                                                              'STATIC_TABLEAU',
                                                                                                              'REVEAL_SUPPORT',
                                                                                                              'COMPONENT_INSPECT',
                                                                                                              'COMPONENT_DIVE_IN',
                                                                                                              'TRACK_TRANSFORMATION',
                                                                                                              'COMPARE_SPLIT',
                                                                                                              'CAUSE_EFFECT_FOLLOW',
                                                                                                              'HANDOFF_CONTACT',
                                                                                                              'CONSEQUENCE_PULLBACK',
                                                                                                              'SYNTHESIS_PULLBACK']},
                                                                                           'shot_scale': {'type': 'string',
                                                                                                          'enum': ['EXTREME_WIDE',
                                                                                                                   'WIDE',
                                                                                                                   'MEDIUM_WIDE',
                                                                                                                   'MEDIUM',
                                                                                                                   'MEDIUM_CLOSE',
                                                                                                                   'CLOSE',
                                                                                                                   'MACRO']},
                                                                                           'angle': {'type': 'string',
                                                                                                     'enum': ['EYE_LEVEL',
                                                                                                              'HIGH',
                                                                                                              'LOW',
                                                                                                              'TOP_DOWN',
                                                                                                              'THREE_QUARTER',
                                                                                                              'PROFILE',
                                                                                                              'FRONTAL']},
                                                                                           'subject_target': {'type': 'string'},
                                                                                           'reveal_framing': {'type': 'string'},
                                                                                           'depth_strategy': {'type': 'string',
                                                                                                              'enum': ['FLAT',
                                                                                                                       'LAYERED',
                                                                                                                       'SHALLOW_FOCUS',
                                                                                                                       'DEEP_FOCUS',
                                                                                                                       'MACRO_DEPTH']},
                                                                                           'camera_atom': {'type': 'object',
                                                                                                           'additionalProperties': False,
                                                                                                           'required': ['atom',
                                                                                                                        'target',
                                                                                                                        'motivation',
                                                                                                                        'intensity',
                                                                                                                        'start_semantic_state',
                                                                                                                        'end_semantic_state'],
                                                                                                           'properties': {'atom': {'type': 'string',
                                                                                                                                   'enum': ['HOLD',
                                                                                                                                            'REFRAME',
                                                                                                                                            'PUSH_IN',
                                                                                                                                            'PULL_BACK',
                                                                                                                                            'PAN',
                                                                                                                                            'TILT',
                                                                                                                                            'TRACK',
                                                                                                                                            'ARC',
                                                                                                                                            'FOLLOW']},
                                                                                                                          'target': {'type': 'string'},
                                                                                                                          'motivation': {'type': 'string'},
                                                                                                                          'intensity': {'type': 'string',
                                                                                                                                        'enum': ['NONE',
                                                                                                                                                 'SUBTLE',
                                                                                                                                                 'MODERATE',
                                                                                                                                                 'STRONG']},
                                                                                                                          'start_semantic_state': {'type': 'string'},
                                                                                                                          'end_semantic_state': {'type': 'string'}}},
                                                                                           'transition_relation': {'type': 'string',
                                                                                                                   'enum': ['HOLD_CONTINUITY',
                                                                                                                            'MATCH_POSITION',
                                                                                                                            'MATCH_ACTION',
                                                                                                                            'CUT_ON_REVEAL',
                                                                                                                            'CARRY_MOTION',
                                                                                                                            'HARD_CUT',
                                                                                                                            'DISSOLVE_MOTIVATED']},
                                                                                           'attention_anchor': {'type': 'string'},
                                                                                           'continuity_reason': {'type': 'string'}}}},
                                                        'global_rules': {'type': 'array', 'items': {'type': 'string'}},
                                                        'risk_notes': {'type': 'array',
                                                                       'items': {'type': 'string'}}}}}}}
EDITORIAL_SCHEMA = {'type': 'object',
 'additionalProperties': False,
 'required': ['candidates'],
 'properties': {'candidates': {'type': 'array',
                               'minItems': 3,
                               'maxItems': 5,
                               'items': {'type': 'object',
                                         'additionalProperties': False,
                                         'required': ['candidate_id',
                                                      'editorial_thesis',
                                                      'project_rate',
                                                      'target_duration_frames',
                                                      'rhythm_profile',
                                                      'peak_budget',
                                                      'beats',
                                                      'final_payoff_hold_frames',
                                                      'risk_notes'],
                                         'properties': {'candidate_id': {'type': 'string'},
                                                        'editorial_thesis': {'type': 'string'},
                                                        'project_rate': {'type': 'integer'},
                                                        'target_duration_frames': {'type': 'integer'},
                                                        'rhythm_profile': {'type': 'string'},
                                                        'peak_budget': {'type': 'integer', 'minimum': 1},
                                                        'beats': {'type': 'array',
                                                                  'minItems': 2,
                                                                  'items': {'type': 'object',
                                                                            'additionalProperties': False,
                                                                            'required': ['beat_id',
                                                                                         'role',
                                                                                         'start',
                                                                                         'duration',
                                                                                         'action_frame',
                                                                                         'settle_frame',
                                                                                         'energy',
                                                                                         'stillness_frames',
                                                                                         'overlap_to_next_frames',
                                                                                         'transition',
                                                                                         'duration_rationale'],
                                                                            'properties': {'beat_id': {'type': 'string'},
                                                                                           'role': {'type': 'string', 'minLength': 1},
                                                                                           'start': {'type': 'object',
                                                                                                     'additionalProperties': False,
                                                                                                     'required': ['value',
                                                                                                                  'rate'],
                                                                                                     'properties': {'value': {'type': 'integer',
                                                                                                                              'minimum': 0},
                                                                                                                    'rate': {'type': 'integer',
                                                                                                                             'minimum': 1}}},
                                                                                           'duration': {'type': 'object',
                                                                                                        'additionalProperties': False,
                                                                                                        'required': ['value',
                                                                                                                     'rate'],
                                                                                                        'properties': {'value': {'type': 'integer',
                                                                                                                                 'minimum': 0},
                                                                                                                       'rate': {'type': 'integer',
                                                                                                                                'minimum': 1}}},
                                                                                           'action_frame': {'type': 'integer',
                                                                                                            'minimum': 0},
                                                                                           'settle_frame': {'type': 'integer',
                                                                                                            'minimum': 1},
                                                                                           'energy': {'type': 'string',
                                                                                                      'enum': ['STILL',
                                                                                                               'LOW',
                                                                                                               'MEDIUM',
                                                                                                               'HIGH',
                                                                                                               'PEAK']},
                                                                                           'stillness_frames': {'type': 'integer',
                                                                                                                'minimum': 0},
                                                                                           'overlap_to_next_frames': {'type': 'integer',
                                                                                                                      'minimum': 0},
                                                                                           'transition': {'type': 'string',
                                                                                                          'enum': ['CUT',
                                                                                                                   'MATCH_CUT',
                                                                                                                   'CARRY',
                                                                                                                   'DISSOLVE_MOTIVATED',
                                                                                                                   'HOLD_THROUGH']},
                                                                                           'duration_rationale': {'type': 'string'}}}},
                                                        'final_payoff_hold_frames': {'type': 'integer', 'minimum': 0},
                                                        'risk_notes': {'type': 'array',
                                                                       'items': {'type': 'string'}}}}}}}
SCHEMAS.update({
    "cinematography": CINEMATOGRAPHY_SCHEMA,
    "cinematography_review": PRODUCER_SCHEMA,
    "showrunner_select_cinematography": SHOWRUNNER_SELECTION_SCHEMA,
    "editorial_rhythm": EDITORIAL_SCHEMA,
    "editorial_review": PRODUCER_SCHEMA,
    "showrunner_select_editorial": SHOWRUNNER_SELECTION_SCHEMA,
    "temporal_storyboard_review": PRODUCER_SCHEMA,
})

MOTION_ACTION_SCHEMA = {
    'type':'object','additionalProperties':False,
    'required':['action_id','beat_id','actor','requested_verb','performer_class','target','prop','semantic_goal','causal_role','dependencies','overlap_policy','anticipation','contact_requirement','ownership_before','ownership_after','settle','reduced_motion','fallback_policy','available_requirements','motivation'],
    'properties':{
        'action_id':{'type':'string'},'beat_id':{'type':'string'},'actor':{'type':'string'},
        'requested_verb':{'type':'string','enum':['HOLD','LOOK','WALK','RUN','SPRINT','SIT','STAND','REACH','POINT','PRESENT','PRESS','TAP','PICKUP','PLACE','CARRY_LIGHT','CARRY_HEAVY','HANDOFF_DIRECT','HANDOFF_PLACE_AND_TAKE','TYPE','PHONE_HOLD','DANCE','REVEAL','HIGHLIGHT','DE_EMPHASIZE','TRACE_FLOW','TRANSFORM','OBJECT_MOVE','TYPE_REVEAL','SETTLE','DRAW','ANNOTATE','ERASE','REFRAME_CONTENT','SCROLL','STATE_CHANGE','SIDESTEP','LATERAL_REPOSITION']},
        'performer_class':{'type':'string','enum':['STICKMAN_V2','HUMANOID','ROBOT','SCENE_GRAPH','WHITEBOARD','PRODUCT_UI','SPECIALIST']},
        'target':{'type':'string'},'prop':{'type':'string'},'semantic_goal':{'type':'string'},'causal_role':{'type':'string'},
        'dependencies':{'type':'array','items':{'type':'string'}},
        'overlap_policy':{'type':'string','enum':['SERIAL_REQUIRED','MAY_OVERLAP','OVERLAP_PREFERRED','HOLD']},
        'anticipation':{'type':'string'},'contact_requirement':{'type':'string','enum':['NONE','TARGET_CONTACT','GRIP_CONTACT','SEAT_CONTACT','SHARED_SUPPORT_CONTACT']},
        'ownership_before':{'type':'string'},'ownership_after':{'type':'string'},'settle':{'type':'string'},'reduced_motion':{'type':'string'},
        'fallback_policy':{'type':'string','enum':['FAIL_CLOSED','ALLOW_SEMANTIC_EQUIVALENT']},
        'available_requirements':{'type':'array','items':{'type':'string'}},'motivation':{'type':'string'}
    }
}
MOTION_SCHEMA = {
    'type':'object','additionalProperties':False,'required':['candidates'],
    'properties':{'candidates':{'type':'array','minItems':3,'maxItems':5,'items':{
        'type':'object','additionalProperties':False,
        'required':['candidate_id','motion_thesis','restraint_strategy','actions','beat_motion_summary','global_rules','risk_notes'],
        'properties':{
            'candidate_id':{'type':'string'},'motion_thesis':{'type':'string'},'restraint_strategy':{'type':'string'},
            'actions':{'type':'array','minItems':1,'items':MOTION_ACTION_SCHEMA},
            'beat_motion_summary':{'type':'array','items':{'type':'object','additionalProperties':False,'required':['beat_id','summary'],'properties':{'beat_id':{'type':'string'},'summary':{'type':'string'}}}},
            'global_rules':{'type':'array','items':{'type':'string'}},'risk_notes':{'type':'array','items':{'type':'string'}}
        }
    }}}
}
SCHEMAS.update({'motion_performance':MOTION_SCHEMA,'motion_review':PRODUCER_SCHEMA,'showrunner_select_motion':SHOWRUNNER_SELECTION_SCHEMA})

SOUND_EVENT_SCHEMA={'type':'object','additionalProperties':False,'required':['event_id','beat_id','kind','semantic_tag','intensity','optional','ducking','narrative_reason','sync_target','silence_before','silence_after'],'properties':{
'event_id':{'type':'string'},'beat_id':{'type':'string'},'kind':{'type':'string','enum':['SFX','FOLEY','TRANSITION','NARRATION_ACCENT','MUSIC_CUE','SILENCE']},'semantic_tag':{'type':'string'},'intensity':{'type':'string','enum':['NONE','SOFT','MEDIUM','STRONG','PEAK']},'optional':{'type':'boolean'},'ducking':{'type':'string','enum':['NONE','LIGHT','MODERATE','STRONG']},'narrative_reason':{'type':'string'},'sync_target':{'type':'string'},'silence_before':{'type':'boolean'},'silence_after':{'type':'boolean'}}}
SOUND_SCHEMA={'type':'object','additionalProperties':False,'required':['candidates'],'properties':{'candidates':{'type':'array','minItems':3,'maxItems':5,'items':{'type':'object','additionalProperties':False,'required':['candidate_id','sound_thesis','narration_strategy','music_strategy','motifs','events','beat_sound_summary','mix_intent','silence_strategy','risk_notes'],'properties':{
'candidate_id':{'type':'string'},'sound_thesis':{'type':'string'},'narration_strategy':{'type':'string'},
'music_strategy':{'type':'object','additionalProperties':False,'required':['mode','full_length_bed','narrative_role','energy_arc','rights_policy'],'properties':{'mode':{'type':'string','enum':['NONE','MOTIF_ONLY','EXISTING_LICENSED','GENERATIVE']},'full_length_bed':{'type':'boolean'},'narrative_role':{'type':'string'},'energy_arc':{'type':'array','items':{'type':'string'}},'rights_policy':{'type':'string'}}},
'motifs':{'type':'array','items':{'type':'string'}},'events':{'type':'array','items':SOUND_EVENT_SCHEMA},
'beat_sound_summary':{'type':'array','items':{'type':'object','additionalProperties':False,'required':['beat_id','summary'],'properties':{'beat_id':{'type':'string'},'summary':{'type':'string'}}}},
'mix_intent':{'type':'object','additionalProperties':False,'required':['narration_priority','ducking_profile','impact_headroom','mastering_intent'],'properties':{'narration_priority':{'type':'string'},'ducking_profile':{'type':'string','enum':['NONE','LIGHT','MODERATE','STRONG']},'impact_headroom':{'type':'string'},'mastering_intent':{'type':'string'}}},
'silence_strategy':{'type':'string'},'risk_notes':{'type':'array','items':{'type':'string'}}}}}}}
SCHEMAS.update({'sound_direction':SOUND_SCHEMA,'sound_review':PRODUCER_SCHEMA,'showrunner_select_sound':SHOWRUNNER_SELECTION_SCHEMA})

FINAL_SCORED_DIMENSION_SCHEMA={
 'type':'object','additionalProperties':False,'required':['score','confidence','rationale'],
 'properties':{'score':{'type':'number','minimum':0,'maximum':10},'confidence':{'type':'string','enum':['LOW','MEDIUM','HIGH']},'rationale':{'type':'string'}}
}
FINAL_HARD_GATE_SCHEMA={
 'type':'object','additionalProperties':False,'required':['dimension','status','code','evidence'],
 'properties':{
  'dimension':{'type':'string','enum':['EVIDENCE_TRUTH','DEPARTMENT_COMPLETENESS','STORY_COHERENCE','STRUCTURAL_VISUAL_INTENT','STRUCTURAL_ART_DIRECTION','STRUCTURAL_CINEMATOGRAPHY_DIRECTION','STRUCTURAL_EDITORIAL_DIRECTION','STRUCTURAL_MOTION_EXECUTABILITY','STRUCTURAL_SOUND_RIGHTS_AND_FUNCTION','FINAL_PAYOFF','TECHNICAL_BODY_VETOES']},
  'status':{'type':'string','enum':['PASS','FAIL','UNKNOWN']},'code':{'type':'string'},'evidence':{'type':'array','items':{'type':'string'}}}
}
FINAL_DEPARTMENT_REVISION_SCHEMA={
 'type':'object','additionalProperties':False,'required':['owner_department','issue_code','required_change','preserve','priority'],
 'properties':{
  'owner_department':{'type':'string','enum':['STORY','VISUAL_CONCEPT','ART_DIRECTION','CINEMATOGRAPHY','EDITORIAL_RHYTHM','MOTION_PERFORMANCE','SOUND_DIRECTION']},
  'issue_code':{'type':'string'},'required_change':{'type':'string'},'preserve':{'type':'array','items':{'type':'string'}},
  'priority':{'type':'string','enum':['HIGH','MEDIUM','LOW']}
 }
}
FINAL_PRODUCER_SCHEMA={
 'type':'object','additionalProperties':False,
 'required':['verdict','hard_gates','craft_scores','taste_judgments','divergence','uncertainty','strengths','issues','revision_plan','department_revisions','commercial_recommendation'],
 'properties':{
  'verdict':{'type':'string','enum':['ACCEPT','REVISE','REJECT','ESCALATE_HUMAN']},
  'hard_gates':{'type':'array','minItems':1,'items':FINAL_HARD_GATE_SCHEMA},
  'craft_scores':{'type':'object','additionalProperties':False,'required':['story_clarity','visual_communication','art_craft','visual_hierarchy','cinematography','editorial_rhythm','motion_intentionality','sound_design','final_payoff','commercial_finish'],'properties':{k:FINAL_SCORED_DIMENSION_SCHEMA for k in ['story_clarity','visual_communication','art_craft','visual_hierarchy','cinematography','editorial_rhythm','motion_intentionality','sound_design','final_payoff','commercial_finish']}},
  'taste_judgments':{'type':'object','additionalProperties':False,'required':['beauty_composition','illustration_quality','charm_appeal','emotional_appropriateness','originality','contextual_appropriateness','commercial_believability','engagement_memorability','authorship_specificity','reference_independence','aesthetic_coherence','emotional_resonance'],'properties':{k:FINAL_SCORED_DIMENSION_SCHEMA for k in ['beauty_composition','illustration_quality','charm_appeal','emotional_appropriateness','originality','contextual_appropriateness','commercial_believability','engagement_memorability','authorship_specificity','reference_independence','aesthetic_coherence','emotional_resonance']}},
  'divergence':{'type':'object','additionalProperties':False,'required':['novelty','conceptual_risk','template_similarity','rationale'],'properties':{'novelty':{'type':'number','minimum':0,'maximum':10},'conceptual_risk':{'type':'number','minimum':0,'maximum':10},'template_similarity':{'type':'number','minimum':0,'maximum':10},'rationale':{'type':'string'}}},
  'uncertainty':{'type':'object','additionalProperties':False,'required':['confidence','reasons','human_review_required','multimodal_evidence_complete'],'properties':{'confidence':{'type':'string','enum':['LOW','MEDIUM','HIGH']},'reasons':{'type':'array','items':{'type':'string'}},'human_review_required':{'type':'boolean'},'multimodal_evidence_complete':{'type':'boolean'}}},
  'strengths':{'type':'array','items':{'type':'string'}},'issues':{'type':'array','items':{'type':'string'}},'revision_plan':{'type':'array','items':{'type':'string'}},
  'department_revisions':{'type':'array','items':FINAL_DEPARTMENT_REVISION_SCHEMA},
  'commercial_recommendation':{'type':'string','enum':['DO_NOT_RENDER','RENDER_FOR_INTERNAL_REVIEW','MACHINE_ACCEPT_HUMAN_REVIEW_REQUIRED','HUMAN_REVIEW_REQUIRED']}
 }
}
SCHEMAS.update({'final_producer':FINAL_PRODUCER_SCHEMA})

PERCEPTUAL_AUDITOR_SCHEMA={
 'type':'object','additionalProperties':False,
 'required':['verdict','checks','veto_reasons','observations'],
 'properties':{
  'verdict':{'type':'string','enum':['PASS','VETO']},
  'checks':{'type':'object','additionalProperties':False,'required':['generic_template_feel','reference_derivation','aesthetic_coherence','emotional_effect','authorship_specificity','payoff','brand_fidelity','audio_visual_coherence','environment_authorship'],'properties':{k:{'type':'string','enum':['PASS','VETO','NOT_APPLICABLE']} for k in ['generic_template_feel','reference_derivation','aesthetic_coherence','emotional_effect','authorship_specificity','payoff','brand_fidelity','audio_visual_coherence','environment_authorship']}},
  'veto_reasons':{'type':'array','items':{'type':'string'}},
  'observations':{'type':'array','items':{'type':'string'}},
 }
}
SCHEMAS.update({'perceptual_auditor':PERCEPTUAL_AUDITOR_SCHEMA})

# P8 V3 creative-openness normalization. Creative descriptions remain open;
# only low-level executable bindings retain finite vocabularies.
def _apply_p8_v3_open_schema_contracts():
    for schema in (VISUAL_SCHEMA,ART_SCHEMA,CINEMATOGRAPHY_SCHEMA,EDITORIAL_SCHEMA,MOTION_SCHEMA,SOUND_SCHEMA):
        candidates=schema.get('properties',{}).get('candidates',{})
        if isinstance(candidates,dict):
            candidates['minItems']=2; candidates.pop('maxItems',None)
    # Visual/Art representation is authored language, not a house enum.
    VISUAL_SCHEMA['properties']['candidates']['items']['properties']['representation']={'type':'string','minLength':1}
    art_item=ART_SCHEMA['properties']['candidates']['items']['properties']
    art_item['form_request']['properties']['representation']={'type':'string','minLength':1}
    art_item['composition']['properties']['support_budget']={'type':'integer','minimum':0}
    art_item['composition']['properties']['decoration_budget']={'type':'integer','minimum':0}
    # Cinematography descriptive language is open. camera_atom remains bounded because it is an execution binding.
    shot=CINEMATOGRAPHY_SCHEMA['properties']['candidates']['items']['properties']['shots']['items']['properties']
    for key in ('idiom','shot_scale','angle','depth_strategy','transition_relation'):
        shot[key]={'type':'string','minLength':1}
    # Editorial purpose/role is open. Frame math and transition mechanics remain executable vocabulary.
    editorial_beat=EDITORIAL_SCHEMA['properties']['candidates']['items']['properties']['beats']['items']['properties']
    editorial_beat['role']={'type':'string','minLength':1}
    editorial_beat['event_id']={'type':'string','minLength':1}
    # Motion creative intent is open and explicit; requested_verb is only the capability-bound primitive.
    if 'semantic_action' not in MOTION_ACTION_SCHEMA['required']:
        MOTION_ACTION_SCHEMA['required'].insert(MOTION_ACTION_SCHEMA['required'].index('requested_verb'),'semantic_action')
    MOTION_ACTION_SCHEMA['properties']['semantic_action']={'type':'string','minLength':1}
_apply_p8_v3_open_schema_contracts()
