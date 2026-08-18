#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json,os,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AD=ROOT/'services/studio-family-engines/editorial_adapter.py'
ER=ROOT/'engines/editorial'
os.environ['STUDIO_EDITORIAL_ENGINE_ROOT']=str(ER)
sys.path.insert(0,str(AD.parent))
spec=importlib.util.spec_from_file_location('editorial_adapter',AD);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks={}
board={'schema':'NexMindCanonicalSoundStoryboardV4','beats':[{'beat_id':'B1','scene_thesis':'One dashboard turns scattered signals into a decision.','hero_identity':'dashboard screen','supporting_assets':['laptop','paper sheet'],'art_direction':{'composition':{'execution_directives':{'spatial_mode':'PRODUCT_STAGE','depth_mode':'DEEP','hero_scale':'DOMINANT_CLOSE','environment_density':'CONTEXTUAL','overlap_mode':'HERO_SUPPORT','typography_mode':'EMBEDDED'}}},'continuity_in':'scattered','continuity_out':'clear','motion_plan_status':'DIRECTED_MOTION_PERFORMANCE','sound_plan_status':'DIRECTED_SOUND','motion_actions':[{'action_id':'A1','performer_class':'SCENE_GRAPH','actor':'dashboard screen','requested_verb':'HIGHLIGHT','execution':{'resolved_verb':'HIGHLIGHT'}}],'sound_events':[{'event_id':'S1','kind':'SILENCE','semantic_tag':'','intensity':'NONE'}],'editorial':{'duration':{'value':4,'rate':1}},'camera':{'beat_id':'B1','idiom':'COMPONENT_INSPECT','shot_scale':'MEDIUM_CLOSE','angle':'EYE_LEVEL','subject_target':'dashboard screen','reveal_framing':'dominant','depth_strategy':'LAYERED','camera_atom':{'atom':'PUSH_IN','target':'dashboard screen','motivation':'clarity resolves','intensity':'SUBTLE','start_semantic_state':'scattered','end_semantic_state':'clear'},'transition_relation':'HOLD_CONTINUITY','attention_anchor':'dashboard','continuity_reason':'same world'}}]}
req={'productionId':'qa','creativeStateArtifactHash':'a'*64,'durationSeconds':4,'aspectRatio':'16:9','brandExecution':{'schema':'StudioBrandExecutionV1','sourceAuthority':'MEMORY_INPUT','memoryInputSnapshotId':'qa-memory','memoryInputSnapshotHash':'b'*64,'brandExecutionHash':'c'*64,'tokens':{}},'finalBoard':board,'referenceMedia':[]}
plan=m._render_plan(req);scene=plan['renderProgram']['scenes'][0];bindings=scene['assetBindings']
checks['p8_hero_bound_as_real_asset']=scene['storyResponsibility']['heroContinuityId'].startswith('hero-') and bindings[0]['semanticEntityId']=='dashboard screen' and bindings[0]['kind']=='literal-prop'
checks['all_p8_supports_survive']=set(scene['adapterTrace']['p8SupportingAssets'])=={'laptop','paper sheet'} and {'laptop','paper sheet'} <= {b['semanticEntityId'] for b in bindings}
checks['generic_icon_not_hero']=all(not (b['role']=='hero' and b.get('kind')=='icon') for b in bindings)
checks['camera_atom_preserved']=scene['camera']['atom']=='PUSH_IN' and scene['camera']['targetContinuityId']==scene['storyResponsibility']['heroContinuityId'] and scene['camera']['scaleEnd']>1
checks['adapter_creative_choice_false']=plan['adapterTrace']['creativeChoiceIntroduced'] is False and scene['adapterTrace']['creativeChoiceIntroduced'] is False
checks['rich_treatment_not_forced_typography_only']=scene['treatmentClass']=='mixed-editorial' and scene['adapterTrace']['boundSupportCount']>=3
checks['execution_only_renderer_import']='editorial_renderer_execution' in AD.read_text() and 'level5_renderer_execution' not in AD.read_text()

checks['p8_art_directives_preserved']=scene['composition']['executionDirectives']=={'spatial_mode':'PRODUCT_STAGE','depth_mode':'DEEP','hero_scale':'DOMINANT_CLOSE','environment_density':'CONTEXTUAL','overlap_mode':'HERO_SUPPORT','typography_mode':'EMBEDDED'} and scene['adapterTrace']['artExecutionDirectives']==scene['composition']['executionDirectives']
renderer_js=(ER/'explainer-motion/faceless-public-levels-v1/renderer/faceless-level5-engine.js').read_text()
checks['renderer_executes_bounded_art_vocabulary']=all(x in renderer_js for x in ['spatial_mode','depth_mode','hero_scale','environment_density','overlap_mode','typography_mode']) and 'artDirectives(scene)' in renderer_js
result={'schema':'EditorialExecutionBodyV2QA','status':'PASS' if all(checks.values()) else 'FAIL','passed':sum(checks.values()),'total':len(checks),'checks':checks}
(ROOT/'reports/EDITORIAL_EXECUTION_BODY_V2_QA.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2));raise SystemExit(0 if result['status']=='PASS' else 1)
