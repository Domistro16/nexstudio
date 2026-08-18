from __future__ import annotations

import json, os, unittest
from pathlib import Path
from unittest.mock import patch
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from nexmind_god_mode.live_provider import LiveCreativeModelProvider, RoleRouter
from nexmind_god_mode.provider import ProviderError


class OperatorModelRoutingTests(unittest.TestCase):
    def test_openai_model_overrides_all_creative_lane_defaults(self):
        with patch.dict(os.environ,{'NEXMIND_CREATIVE_MODEL':'virtuals/creative-model-x'},clear=True):
            r=RoleRouter()
            for task in ['source_understanding','story','visual','art','cinematography','editorial_rhythm','motion_performance','sound_direction']:
                self.assertEqual(r.resolve(task).model,'virtuals/creative-model-x',task)

    def test_review_lane_model_overrides_all_review_lane_defaults(self):
        with patch.dict(os.environ,{'NEXMIND_REVIEW_MODEL':'virtuals/reviewer-model-y','NEXMIND_REVIEW_BASE_URL':'https://virtuals.invalid/v1','NEXMIND_REVIEW_INPUT_MODALITIES':'images,audio','NEXMIND_REVIEW_AUDIO_INPUT_MODE':'chat_input_audio'},clear=True):
            r=RoleRouter()
            for task in ['producer','showrunner_select','art_review','showrunner_select_art','storyboard_review','cinematography_review','showrunner_select_cinematography','editorial_review','showrunner_select_editorial','temporal_storyboard_review','motion_review','showrunner_select_motion','sound_review','showrunner_select_sound','final_producer']:
                self.assertEqual(r.resolve(task).model,'virtuals/reviewer-model-y',task)

    def test_role_specific_model_has_highest_precedence(self):
        with patch.dict(os.environ,{
            'NEXMIND_CREATIVE_MODEL':'virtuals/creative-global',
            'NEXMIND_STORY_DIRECTOR_MODEL':'virtuals/story-special',
        },clear=True):
            r=RoleRouter()
            self.assertEqual(r.resolve('story').model,'virtuals/story-special')
            self.assertEqual(r.resolve('visual').model,'virtuals/creative-global')

    def test_logical_lane_aliases_work_when_provider_model_vars_absent(self):
        with patch.dict(os.environ,{
            'NEXMIND_CREATIVE_MODEL':'virtuals/creative-lane',
            'NEXMIND_REVIEW_MODEL':'virtuals/review-lane',
            'NEXMIND_REVIEW_BASE_URL':'https://virtuals.invalid/v1',
        },clear=True):
            r=RoleRouter()
            self.assertEqual(r.resolve('story').model,'virtuals/creative-lane')
            self.assertEqual(r.resolve('producer').model,'virtuals/review-lane')

    def test_provider_label_alone_cannot_smuggle_a_model_from_another_lane(self):
        with patch.dict(os.environ,{
            'NEXMIND_STORY_DIRECTOR_PROVIDER':'agentrouter',
            'NEXMIND_REVIEW_MODEL':'virtuals/review-only-model',
            'NEXMIND_REVIEW_BASE_URL':'https://virtuals.invalid/v1',
        },clear=True):
            with self.assertRaisesRegex(ProviderError,'NO_COMPATIBLE_MODEL_CONFIG'):
                RoleRouter().resolve('story')

    def test_prompt_json_payload_sends_operator_model_verbatim(self):
        with patch.dict(os.environ,{
            'NEXMIND_PROMPT_JSON_COMPAT':'1',
            'NEXMIND_CREATIVE_MODEL':'Qwen/Qwen3-235B-A22B-Instruct-2507',
        },clear=True):
            p=LiveCreativeModelProvider()
            route=RoleRouter().resolve('story')
            payload=p._prompt_json_payload('story',{'production_id':'P'},route)
            self.assertEqual(payload['model'],'Qwen/Qwen3-235B-A22B-Instruct-2507')

    def test_prompt_json_review_payload_sends_operator_model_verbatim(self):
        with patch.dict(os.environ,{
            'NEXMIND_PROMPT_JSON_COMPAT':'1',
            'NEXMIND_REVIEW_MODEL':'deepseek/deepseek-v3.2',
            'NEXMIND_REVIEW_BASE_URL':'https://virtuals.invalid/v1',
        },clear=True):
            p=LiveCreativeModelProvider()
            route=RoleRouter().resolve('producer')
            payload=p._prompt_json_payload('producer',{'production_id':'P'},route)
            self.assertEqual(payload['model'],'deepseek/deepseek-v3.2')

    def test_ambiguous_operator_model_is_still_rejected(self):
        with patch.dict(os.environ,{'NEXMIND_CREATIVE_MODEL':'latest'},clear=True):
            with self.assertRaisesRegex(ProviderError,'ambiguous model alias'):
                RoleRouter().resolve('story')

    def test_no_model_configuration_fails_closed_without_named_default(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(ProviderError,'NO_COMPATIBLE_MODEL_CONFIG'):
                RoleRouter().resolve('story')

    def test_source_understanding_accepts_dedicated_or_creative_reasoning_capability(self):
        dedicated={"routes":[
            {"provider":"source-gateway","model":"source-specialist","capabilities":["source_reasoning"],"priority":5,"base_url":"https://source.invalid/v1","api_key_env":"SOURCE_KEY"},
            {"provider":"creative-gateway","model":"creative-general","capabilities":["creative_reasoning"],"priority":1,"base_url":"https://creative.invalid/v1","api_key_env":"CREATIVE_KEY"},
        ]}
        with patch.dict(os.environ,{"NEXMIND_MODEL_REGISTRY_JSON":json.dumps(dedicated)},clear=True):
            route=RoleRouter().resolve('source_understanding')
            self.assertEqual((route.provider,route.model),("source-gateway","source-specialist"))
        compatible={"routes":[
            {"provider":"creative-gateway","model":"creative-general","capabilities":["creative_reasoning"],"priority":3,"base_url":"https://creative.invalid/v1","api_key_env":"CREATIVE_KEY"},
        ]}
        with patch.dict(os.environ,{"NEXMIND_MODEL_REGISTRY_JSON":json.dumps(compatible)},clear=True):
            route=RoleRouter().resolve('source_understanding')
            self.assertEqual((route.provider,route.model),("creative-gateway","creative-general"))

    def test_source_visual_understanding_requires_declared_multimodal_capability(self):
        registry={"routes":[
            {"provider":"vision-gateway","model":"vision-source","capabilities":["multimodal_source_understanding"],"input_modalities":["images"],"priority":4,"base_url":"https://vision.invalid/v1","api_key_env":"VISION_KEY"},
            {"provider":"text-gateway","model":"text-only","capabilities":["creative_reasoning"],"priority":9,"base_url":"https://text.invalid/v1","api_key_env":"TEXT_KEY"},
        ]}
        with patch.dict(os.environ,{"NEXMIND_MODEL_REGISTRY_JSON":json.dumps(registry)},clear=True):
            route=RoleRouter().resolve('source_visual_understanding')
            self.assertEqual((route.provider,route.model),("vision-gateway","vision-source"))
        with patch.dict(os.environ,{"NEXMIND_CREATIVE_MODEL":"text-only"},clear=True):
            with self.assertRaisesRegex(ProviderError,'NO_COMPATIBLE_MODEL_CONFIG'):
                RoleRouter().resolve('source_visual_understanding')

    def test_capability_registry_selects_runtime_model_by_capability_and_priority(self):
        registry={"routes":[
            {"provider":"gateway-a","model":"reasoning-small","capabilities":["creative_reasoning"],"priority":1,"base_url":"https://a.invalid/v1","api_key_env":"A_KEY"},
            {"provider":"gateway-b","model":"reasoning-best","capabilities":["creative_reasoning","commercial_creative_selection"],"priority":9,"base_url":"https://b.invalid/v1","api_key_env":"B_KEY"}
        ]}
        with patch.dict(os.environ,{"NEXMIND_MODEL_REGISTRY_JSON":json.dumps(registry)},clear=True):
            route=RoleRouter().resolve('story')
            self.assertEqual((route.provider,route.model),("gateway-b","reasoning-best"))

    def test_gateway_model_does_not_mutate_to_canonical_default(self):
        chosen='virtuals/my-exact-model-id:2026-08'
        with patch.dict(os.environ,{'NEXMIND_CREATIVE_MODEL':chosen},clear=True):
            self.assertEqual(RoleRouter().resolve('story').model,chosen)

    def test_one_model_one_api_key_can_route_every_nexmind_role(self):
        registry={"routes":[{
            "provider":"one-gateway",
            "model":"one-capable-model-v1",
            "capabilities":["*"],
            "input_modalities":["images","audio"],
            "audio_input_mode":"chat_input_audio",
            "priority":100,
            "base_url":"https://one.invalid/v1",
            "api_key_env":"ONE_API_KEY",
        }]}
        tasks=list(RoleRouter.ROLE_NAMES.keys())
        with patch.dict(os.environ,{"NEXMIND_MODEL_REGISTRY_JSON":json.dumps(registry),"ONE_API_KEY":"secret"},clear=True):
            routes=[RoleRouter().resolve(task) for task in tasks]
        self.assertTrue(routes)
        self.assertEqual({r.model for r in routes},{"one-capable-model-v1"})
        self.assertEqual({r.provider for r in routes},{"one-gateway"})
        self.assertEqual({r.api_key_env for r in routes},{"ONE_API_KEY"})
        self.assertTrue(all(r.model=="one-capable-model-v1" for r in routes))



if __name__=='__main__':
    unittest.main(verbosity=2)
