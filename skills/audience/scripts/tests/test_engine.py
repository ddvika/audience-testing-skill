import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audience_core.engine import new_run,advance,validate_decision,clean_snapshot,model_messages,redact
from audience_core.openrouter import AudienceError,BudgetExceeded

class Client:
 def __init__(self,reply):self.reply=reply;self.ledger=[]
 def complete_json(self,*args,**kwargs):
  if isinstance(self.reply,Exception):raise self.reply
  return self.reply

class EngineTests(unittest.TestCase):
 def setUp(self):
  self.plan={'task':'Find the price','url':'https://example.org','max_steps':3,'personas':[{'id':'p001','model':'a/model','goal':'Find price','scenario_modes':['first_use','regular']} ]}
  self.obs={'url':'https://example.org','title':'Product','text':'Price $10','elements':[{'id':'1','role':'button','name':'Details'}]}
  self.catalogue=[{'id':'a/model'}]
 def test_host_action_requires_actual_confirmation(self):
  run=new_run(self.plan);client=Client({'action':{'type':'click','target':'1'}})
  result=advance(run,'p001-first_use',self.obs,client,self.catalogue)
  self.assertEqual(result['action']['target'],'1')
  with self.assertRaises(AudienceError):advance(run,'p001-first_use',self.obs,client,self.catalogue)
  client.reply={'action':{'type':'finish'},'feedback':{'outcome':'success','evidence_ids':['p001-first_use:e002'],'rating':9}}
  result=advance(run,'p001-first_use',self.obs,client,self.catalogue,{'status':'ok'})
  self.assertEqual(result['status'],'completed');self.assertEqual(len(run['sessions'][0]['events']),2)
 def test_repeat_requires_first_session(self):
  with self.assertRaises(AudienceError):advance(new_run(self.plan),'p001-regular',self.obs,Client({}),self.catalogue)
 def test_live_model_flat_action_is_normalized_without_bypassing_validation(self):
  result=validate_decision({'action':'click','target':'1'},self.obs,set())
  self.assertEqual(result['action'],{'type':'click','target':'1'})
  with self.assertRaises(AudienceError):validate_decision({'action':'execute_code','code':'bad'},self.obs,set())
 def test_unknown_target_and_unsupported_tool_rejected(self):
  for action in [{'type':'click','target':'invented'},{'type':'shell','value':'rm -rf'}]:
   with self.assertRaises(AudienceError):validate_decision({'action':action},self.obs,set())
 def test_uncited_success_is_not_counted(self):
  result=validate_decision({'action':{'type':'finish'},'feedback':{'outcome':'success','rating':True,'evidence_ids':['invented']}},self.obs,set())
  self.assertEqual(result['feedback']['outcome'],'partial');self.assertIsNone(result['feedback']['rating'])
 def test_blocked_step_is_not_feedback_failure(self):
  run=new_run(self.plan);client=Client({'action':{'type':'click','target':'1'}})
  advance(run,'p001-first_use',self.obs,client,self.catalogue)
  result=advance(run,'p001-first_use',self.obs,client,self.catalogue,{'status':'blocked','reason':'Login'})
  self.assertEqual(result['status'],'blocked');self.assertEqual(run['sessions'][0]['feedback'],{})
 def test_budget_exhaustion_is_a_separate_status(self):
  result=advance(new_run(self.plan),'p001-first_use',self.obs,Client(BudgetExceeded('limit')),self.catalogue)
  self.assertEqual(result['status'],'budget_limit')
 def test_secret_and_sensitive_elements_redacted(self):
  sample='sk-or-v1-'+'x'*40
  clean=clean_snapshot({**self.obs,'text':sample,'elements':[{'id':'password','input_type':'password'}]})
  self.assertNotIn(sample,str(clean));self.assertEqual(clean['elements'],[])
 def test_prompt_bound_with_large_unicode_page(self):
  run=new_run(self.plan)
  messages=model_messages(run,run['sessions'][0],clean_snapshot({**self.obs,'text':'я'*20000}))
  import json
  self.assertLessEqual(len(json.dumps(messages,ensure_ascii=False).encode()),12000)
 def test_malformed_feedback_arrays_do_not_crash_after_billing(self):
  result=validate_decision({'action':{'type':'finish'},'feedback':{'outcome':'partial','likes':None,'dislikes':7,'evidence_ids':None,'recommendations':{}}},self.obs,set())
  self.assertEqual(result['feedback']['likes'],[])
 def test_select_options_are_visible_to_model(self):
  clean=clean_snapshot({**self.obs,'elements':[{'id':'s','role':'combobox','options':[{'value':'a','label':'Alpha'}]}]})
  self.assertEqual(clean['elements'][0]['options'][0]['value'],'a')

 def test_satisfaction_and_nps_have_distinct_valid_scales(self):
  feedback={'outcome':'success','rating':9,'evidence_ids':['e1'],
   'assessment':{'satisfaction':2,'effort':5,'purpose_clear':False,'next_step_clear':True,
                 'result_clear':True,'evidence_ids':['e1','e1','unknown']}}
  value=validate_decision({'action':{'type':'finish'},'feedback':feedback},self.obs,{'e1'})['feedback']
  self.assertEqual(value['rating'],9)
  self.assertEqual(value['assessment']['satisfaction'],2)
  self.assertEqual(value['assessment']['effort'],5)
  self.assertFalse(value['assessment']['purpose_clear'])
  self.assertEqual(value['assessment']['evidence_ids'],['e1'])
 def test_unsupported_judgments_become_unknown_not_negative(self):
  feedback={'outcome':'partial','rating':10,'return_intent':True,'evidence_ids':['missing'],
   'assessment':{'satisfaction':5,'effort':1,'purpose_clear':True,'evidence_ids':['missing']}}
  value=validate_decision({'action':{'type':'finish'},'feedback':feedback},self.obs,{'e1'})['feedback']
  self.assertIsNone(value['rating']);self.assertIsNone(value['return_intent'])
  self.assertTrue(all(value['assessment'][k] is None for k in ('satisfaction','effort','purpose_clear')))
  self.assertEqual(value['assessment']['evidence_ids'],[])
 def test_invalid_assessment_and_journey_types_are_not_coerced(self):
  feedback={'outcome':'partial','evidence_ids':['e1'],
   'assessment':{'satisfaction':True,'effort':0,'purpose_clear':'yes','result_clear':False,'evidence_ids':['e1']},
   'journey':[{'stage':[], 'reached':True,'evidence_ids':['e1']},
              {'stage':'start','reached':'yes','evidence_ids':['e1']},
              {'stage':'result','reached':True,'evidence_ids':['missing']},
              {'stage':'entry','reached':True,'evidence_ids':['e1']}]}
  value=validate_decision({'action':{'type':'finish'},'feedback':feedback},self.obs,{'e1'})['feedback']
  self.assertIsNone(value['assessment']['satisfaction']);self.assertIsNone(value['assessment']['effort'])
  self.assertIsNone(value['assessment']['purpose_clear']);self.assertFalse(value['assessment']['result_clear'])
  self.assertEqual(value['journey'],[{'stage':'entry','reached':True,'evidence_ids':['e1']}])
 def test_recommendation_retains_concrete_change_and_valid_refs_only(self):
  rec={'change':'Показать, что заявка ещё не отправлена','reason':'На странице нет подтверждения',
       'stage':'result','scope':'flow','issue_key':'unclear_completion','observed':'Виден только черновик',
       'proposed':'Добавить статус и кнопку подтверждения','expected_metric':'Доля успешных задач',
       'how_to_verify':'Повторить сценарий после изменения','evidence_ids':['e1','bad']}
  value=validate_decision({'action':{'type':'finish'},'feedback':{'outcome':'partial','evidence_ids':['e1'],
     'recommendations':[rec,{**rec,'evidence_ids':['bad']}]}},self.obs,{'e1'})['feedback']
  self.assertEqual(len(value['recommendations']),1)
  self.assertEqual(value['recommendations'][0],{**rec,'evidence_ids':['e1']})
 def test_first_visit_cannot_count_return_stage(self):
  run=new_run(self.plan);eid='p001-first_use:e001'
  client=Client({'action':{'type':'finish'},'feedback':{'outcome':'success','evidence_ids':[eid],
     'journey':[{'stage':'return','reached':True,'evidence_ids':[eid]}]}})
  advance(run,'p001-first_use',self.obs,client,self.catalogue)
  self.assertEqual(run['sessions'][0]['feedback']['journey'],[])
 def test_repeat_prompt_uses_specific_new_goal_and_recorded_history(self):
  self.plan['personas'][0]['scenario_goals']={'first_use':'Find a concert','regular':'Find another concert next weekend'}
  run=new_run(self.plan);run['sessions'][0].update(status='completed',feedback={'outcome':'success','summary':'Found a concert','evidence_ids':['first']})
  import json
  payload=json.loads(model_messages(run,run['sessions'][1],self.obs)[1]['content'])
  self.assertEqual(payload['goal_for_this_visit'],'Find another concert next weekend')
  self.assertEqual(payload['prior_sessions'][0]['feedback']['summary'],'Found a concert')
 def test_reported_access_barrier_is_not_a_product_failure(self):
  run=new_run(self.plan);eid='p001-first_use:e001'
  result=advance(run,'p001-first_use',self.obs,Client({'action':{'type':'finish'},'block':{
     'reason':'Account sign-in required','evidence_ids':[eid]}}),self.catalogue)
  self.assertEqual(result['status'],'blocked');self.assertEqual(run['sessions'][0]['feedback'],{})
  self.assertEqual(run['sessions'][0]['blocked_evidence_ids'],[eid])
 def test_measured_viewport_is_preserved_and_invalid_values_are_dropped(self):
  self.assertEqual(clean_snapshot({**self.obs,'viewport':{'width':390,'height':844}})['viewport'],{'width':390,'height':844})
  self.assertNotIn('viewport',clean_snapshot({**self.obs,'viewport':{'width':True,'height':844}}))
  self.assertNotIn('viewport',clean_snapshot({**self.obs,'viewport':{'width':'390','height':844}}))
 def test_runtime_output_request_stays_within_planning_bound_and_provider_limit(self):
  from audience_core.planner import OUTPUT_TOKEN_BOUND
  class Capture(Client):
   def complete_json(self,*args,**kwargs):self.tokens=kwargs['max_tokens'];return {'action':{'type':'click','target':'1'}}
  for provider_limit in (None,1000,4000):
   client=Capture({});catalogue=[{'id':'a/model','top_provider':{'max_completion_tokens':provider_limit}}]
   advance(new_run(self.plan),'p001-first_use',self.obs,client,catalogue)
   self.assertLessEqual(client.tokens,OUTPUT_TOKEN_BOUND)
   if provider_limit:self.assertLessEqual(client.tokens,provider_limit)

 def test_final_call_collects_feedback_without_inventing_abandonment(self):
  run=new_run(self.plan);run['sessions'][0]['decisions']=2
  import json
  payload=json.loads(model_messages(run,run['sessions'][0],self.obs)[1]['content'])
  self.assertEqual(payload['decision_calls_remaining'],1)
  eid='p001-first_use:e001'
  client=Client({'action':{'type':'finish'},'feedback':{'outcome':'partial','stop_reason':'decision_limit',
      'evidence_ids':[eid],'summary':'Task still unfinished','assessment':{'effort':4,'evidence_ids':[eid]}}})
  result=advance(run,'p001-first_use',self.obs,client,self.catalogue)
  self.assertEqual(result['status'],'step_limit')
  self.assertEqual(run['sessions'][0]['stop_reason'],'decision_limit')
  self.assertEqual(run['sessions'][0]['feedback']['assessment']['effort'],4)
 def test_early_stop_cannot_misreport_reaching_the_decision_limit(self):
  run=new_run(self.plan);eid='p001-first_use:e001'
  client=Client({'action':{'type':'finish'},'feedback':{'outcome':'partial','stop_reason':'decision_limit','evidence_ids':[eid]}})
  result=advance(run,'p001-first_use',self.obs,client,self.catalogue)
  self.assertEqual(result['status'],'abandoned')
  self.assertNotIn('stop_reason',run['sessions'][0]['feedback'])

 def test_disabled_flags_are_preserved_as_booleans(self):
  clean=clean_snapshot({**self.obs,'elements':[{'id':'off','role':'button','disabled':True},
      {'id':'on','role':'button','disabled':False},{'id':'unknown','disabled':'false'},
      {'id':'s','role':'combobox','options':[{'value':'a','label':'A','disabled':True},
          {'value':'b','label':'B','disabled':False},{'value':'c','label':'C','disabled':'false'}]}]})
  self.assertIs(clean['elements'][0]['disabled'],True)
  self.assertIs(clean['elements'][1]['disabled'],False)
  self.assertNotIn('disabled',clean['elements'][2])
  self.assertIs(clean['elements'][3]['options'][0]['disabled'],True)
  self.assertIs(clean['elements'][3]['options'][1]['disabled'],False)
  self.assertNotIn('disabled',clean['elements'][3]['options'][2])
 def test_disabled_target_is_invalid_model_decision_not_executed_policy_block(self):
  obs={**self.obs,'elements':[{'id':'1','role':'button','name':'Next','disabled':True}]}
  for kind in ('click','fill','select'):
   with self.subTest(kind=kind),self.assertRaisesRegex(AudienceError,'disabled element'):
    validate_decision({'action':{'type':kind,'target':'1','value':'a'}},clean_snapshot(obs),set())
  run=new_run(self.plan)
  result=advance(run,'p001-first_use',obs,Client({'action':{'type':'click','target':'1'}}),self.catalogue)
  self.assertEqual(result['status'],'error')
  self.assertNotIn('pending_action',run['sessions'][0])
  self.assertEqual(run['sessions'][0]['events'][0]['action']['type'],'observe')
  self.assertTrue(run['sessions'][0]['events'][0]['observation']['elements'][0]['disabled'])
 def test_select_requires_captured_enabled_option(self):
  obs=clean_snapshot({**self.obs,'elements':[{'id':'s','role':'combobox','disabled':False,
     'options':[{'value':'off','label':'Unavailable','disabled':True},
                {'value':'on','label':'Available','disabled':False}]}]})
  for value in ('off','invented'):
   with self.subTest(value=value),self.assertRaisesRegex(AudienceError,'unavailable or disabled'):
    validate_decision({'action':{'type':'select','target':'s','value':value}},obs,set())
  valid=validate_decision({'action':{'type':'select','target':'s','value':'on'}},obs,set())
  self.assertEqual(valid['action']['value'],'on')
 def test_disabled_ui_can_still_support_product_obstacle_feedback(self):
  obs={**self.obs,'text':'Continue is disabled. No explanation or prerequisite is visible.',
       'elements':[{'id':'1','role':'button','name':'Continue','disabled':True}]}
  eid='p001-first_use:e001';run=new_run(self.plan)
  feedback={'outcome':'partial','summary':'Continue is disabled and its prerequisite is unclear.',
      'evidence_ids':[eid],'assessment':{'next_step_clear':False,'evidence_ids':[eid]},
      'recommendations':[{'change':'Explain how to enable Continue','reason':'No prerequisite is visible',
         'stage':'start','scope':'flow','evidence_ids':[eid]}]}
  result=advance(run,'p001-first_use',obs,Client({'action':{'type':'finish'},'feedback':feedback}),self.catalogue)
  self.assertEqual(result['status'],'abandoned')
  self.assertFalse(run['sessions'][0]['feedback']['assessment']['next_step_clear'])
  self.assertEqual(run['sessions'][0]['feedback']['recommendations'][0]['evidence_ids'],[eid])

if __name__=='__main__':unittest.main()
