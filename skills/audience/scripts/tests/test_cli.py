import asyncio
import contextlib
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import audience as cli

class FakeClient:
 def __init__(self,*args,**kwargs):self.ledger=[];self.spent_usd=0
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def close(self):pass
 def list_models(self):return [{'id':'fixture/model'}]
 def complete_json(self,model,messages,max_tokens):
  payload=json.loads(messages[1]['content'])
  return {'action':{'type':'finish'},'feedback':{'outcome':'success','rating':9,'evidence_ids':[payload['recent_events'][-1]['id']], 'summary':'Recorded fixture result'}}

class FakeBrowser:
 contexts=[]
 def __init__(self,url,origins,**kwargs):self.url=url;self.kwargs=kwargs;self.closed=False;self.navigations=0;self.contexts.append(self)
 async def start(self):return self
 async def snapshot(self):return {'url':self.url,'title':'Fixture','text':'Result is visible','elements':[]}
 async def act(self,action):self.navigations+=1;return {'status':'ok','snapshot':await self.snapshot()}
 async def close(self):self.closed=True

PLAN={'url':'https://example.org','task':'Read result','max_steps':3,'budget_usd':1,'models':[{'id':'fixture/model','count':2}], 'personas':[
 {'id':'p1','model':'fixture/model','goal':'Read result','device':'mobile','scenario_modes':['first_use','regular']},
 {'id':'p2','model':'fixture/model','goal':'Read result','device':'desktop','scenario_modes':['first_use']}]}

class CLITests(unittest.TestCase):
 def args(self,d):return SimpleNamespace(output=d,budget=1,url='https://example.org',allow_origin=[],site_mode='production',forecast_inputs=None,concurrency=2,screenshots=False,snapshot=None)
 def test_standalone_orchestrates_isolated_personas_and_keeps_repeat_context(self):
  class TaskBrowser(FakeBrowser):
   async def snapshot(self):
    completed=getattr(self,'completed',False)
    return {'url':self.url,'title':'Fixture','text':'Result is visible' if completed else 'Generate your result',
            'task_state':'completed' if completed else 'idle',
            'elements':[{'id':'generate','role':'button','name':'Generate result','disabled':False}]}
   async def act(self,action):
    self.completed=action['type']=='click'
    return await super().act(action)
  class TaskClient(FakeClient):
   def complete_json(self,model,messages,max_tokens):
    payload=json.loads(messages[1]['content'])
    if payload['observation'].get('task_state')=='idle':return {'action':{'type':'click','target':'generate'}}
    return super().complete_json(model,messages,max_tokens)
  FakeBrowser.contexts=[]
  with tempfile.TemporaryDirectory() as d,patch.object(cli,'OpenRouterClient',TaskClient),patch.object(cli,'key_for',return_value='fixture'),patch.object(cli,'plan_for',return_value=PLAN),patch('audience_core.browser.BrowserSession',TaskBrowser),contextlib.redirect_stdout(io.StringIO()):
   asyncio.run(cli.standalone(self.args(d)))
   run=json.loads((Path(d)/'run.json').read_text())
   self.assertEqual(len(run['sessions']),3);self.assertTrue(all(s['status']=='completed' for s in run['sessions']))
   contexts=FakeBrowser.contexts
   self.assertEqual(len(contexts),3) # scout + one context per persona, not per visit
   self.assertEqual(contexts[1].kwargs['viewport'],{'width':390,'height':844})
   self.assertEqual(contexts[1].navigations,3);self.assertTrue(all(c.closed for c in contexts))
   self.assertTrue((Path(d)/'report.html').exists())

 def test_blocked_scout_saves_preflight_without_paid_planning_or_fake_personas(self):
  class BlockedScout(FakeBrowser):
   async def snapshot(self):
    return {**await super().snapshot(),'policy_barriers':['State-changing HTTP methods are blocked.']}
  with tempfile.TemporaryDirectory() as d,patch.object(cli,'OpenRouterClient',FakeClient),patch.object(cli,'key_for',return_value='fixture'),patch.object(cli,'plan_for') as planner,patch.object(FakeClient,'complete_json') as paid,patch('audience_core.browser.BrowserSession',BlockedScout),contextlib.redirect_stdout(io.StringIO()):
   asyncio.run(cli.standalone(self.args(d)))
   run=json.loads((Path(d)/'run.json').read_text())
   planner.assert_not_called();paid.assert_not_called()
   self.assertEqual(run['sessions'],[]);self.assertEqual(run['plan']['personas'],[])
   self.assertEqual(run['preflight']['status'],'blocked')
   self.assertEqual(run['preflight']['observation']['text'],'Result is visible')
   self.assertTrue(run['warnings'])
   self.assertIn('Предварительный просмотр остановлен',(Path(d)/'report.html').read_text())

 def test_persona_startup_barrier_is_recorded_and_never_sent_to_model(self):
  class StartupBarrier(FakeBrowser):
   count=0
   def __init__(self,*args,**kwargs):
    super().__init__(*args,**kwargs);type(self).count+=1;self.is_scout=type(self).count==1
   async def snapshot(self):
    value=await super().snapshot()
    if not self.is_scout:value['policy_barriers']=['Initial API request was blocked.']
    return value
  plan=copy.deepcopy(PLAN);plan['personas']=plan['personas'][:1];plan['personas'][0]['scenario_modes']=['first_use']
  with tempfile.TemporaryDirectory() as d,patch.object(cli,'OpenRouterClient',FakeClient),patch.object(cli,'key_for',return_value='fixture'),patch.object(cli,'plan_for',return_value=plan),patch.object(FakeClient,'complete_json') as paid,patch('audience_core.browser.BrowserSession',StartupBarrier),contextlib.redirect_stdout(io.StringIO()):
   asyncio.run(cli.standalone(self.args(d)))
   run=json.loads((Path(d)/'run.json').read_text());report=json.loads((Path(d)/'report.json').read_text())
   paid.assert_not_called()
   session=run['sessions'][0]
   self.assertEqual(session['status'],'blocked')
   self.assertEqual(session['events'][0]['action']['type'],'observe')
   self.assertEqual(session['events'][0]['observation']['text'],'Result is visible')
   self.assertEqual(report['metrics']['eligible'],0);self.assertEqual(report['metrics']['nps_n'],0)

 def test_background_barrier_between_action_and_next_decision_prevents_second_call(self):
  class BackgroundBarrier(FakeBrowser):
   async def act(self,action):
    result=await super().act(action)
    self.background_block=True
    return result
   async def snapshot(self):
    value=await super().snapshot()
    if getattr(self,'background_block',False):
     value['policy_barriers']=['Background API request was blocked.'];self.background_block=False
    return value
  plan=copy.deepcopy(PLAN);plan['personas']=plan['personas'][:1];plan['personas'][0]['scenario_modes']=['first_use']
  with tempfile.TemporaryDirectory() as d,patch.object(cli,'OpenRouterClient',FakeClient),patch.object(cli,'key_for',return_value='fixture'),patch.object(cli,'plan_for',return_value=plan),patch.object(FakeClient,'complete_json',return_value={'action':{'type':'scroll'}}) as paid,patch('audience_core.browser.BrowserSession',BackgroundBarrier),contextlib.redirect_stdout(io.StringIO()):
   asyncio.run(cli.standalone(self.args(d)))
   run=json.loads((Path(d)/'run.json').read_text());report=json.loads((Path(d)/'report.json').read_text())
   self.assertEqual(paid.call_count,1)
   session=run['sessions'][0]
   self.assertEqual(session['status'],'blocked');self.assertEqual(len(session['events']),2)
   self.assertEqual(session['events'][1]['action']['type'],'scroll')
   self.assertEqual(session['events'][1]['result']['status'],'blocked')
   self.assertEqual(report['metrics']['eligible'],0);self.assertEqual(report['metrics']['task_non_success'],0)

 def test_barrier_during_terminal_model_call_overrides_feedback_and_retains_charge(self):
  for outcome,stop_reason in [('success',None),('failure',None),('partial','decision_limit')]:
   with self.subTest(outcome=outcome):
    class TerminalBarrier(FakeBrowser):
     async def snapshot(self):
      value=await super().snapshot()
      if getattr(self,'background_block',False):
       value.update(text='Results unavailable after blocked request',policy_barriers=['API request blocked while model was deciding.'])
       self.background_block=False
      return value
    class FinishingClient(FakeClient):
     calls=0
     def complete_json(self,model,messages,max_tokens):
      type(self).calls+=1
      TerminalBarrier.contexts[-1].background_block=True
      self.spent_usd+=.001
      self.ledger.append({'cost_status':'actual','cost_usd':.001,'accounted_usd':.001,'requested_model':'fixture/model'})
      payload=json.loads(messages[1]['content'])
      feedback={'outcome':outcome,'rating':9,'return_intent':True,'evidence_ids':[payload['recent_events'][-1]['id']]}
      if stop_reason:feedback['stop_reason']=stop_reason
      return {'action':{'type':'finish'},'feedback':feedback}
    plan=copy.deepcopy(PLAN);plan['max_steps']=1;plan['personas']=plan['personas'][:1];plan['personas'][0]['scenario_modes']=['first_use']
    with tempfile.TemporaryDirectory() as d,patch.object(cli,'OpenRouterClient',FinishingClient),patch.object(cli,'key_for',return_value='fixture'),patch.object(cli,'plan_for',return_value=plan),patch('audience_core.browser.BrowserSession',TerminalBarrier),contextlib.redirect_stdout(io.StringIO()):
     asyncio.run(cli.standalone(self.args(d)))
     run=json.loads((Path(d)/'run.json').read_text());report=json.loads((Path(d)/'report.json').read_text())
     session=run['sessions'][0]
     self.assertEqual(FinishingClient.calls,1)
     self.assertEqual(session['status'],'blocked');self.assertEqual(session['feedback'],{})
     self.assertEqual(len(session['events']),2)
     self.assertEqual(session['events'][-1]['observation']['text'],'Results unavailable after blocked request')
     self.assertEqual(session['events'][-1]['result']['status'],'blocked')
     self.assertEqual(report['metrics']['eligible'],0);self.assertEqual(report['metrics']['nps_n'],0)
     self.assertEqual(report['costs']['confirmed_usd'],.001);self.assertEqual(len(run['ledger']),1)
 def test_host_rejects_nonobject_then_keeps_protocol_alive(self):
  with tempfile.TemporaryDirectory() as d,patch.object(cli,'OpenRouterClient',FakeClient),patch.object(cli,'key_for',return_value='fixture'),patch.object(cli,'plan_for',return_value=PLAN),patch.object(sys,'stdin',io.StringIO('[]\n{"command":"quit"}\n')),contextlib.redirect_stdout(io.StringIO()) as output:
   cli.host(self.args(d))
   rows=[json.loads(x) for x in output.getvalue().splitlines()]
   self.assertIn('error',rows[1]);self.assertIn('reports',rows[2])
 def test_offline_report_uses_durable_costs_after_interruption(self):
  captured=[]
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'run.json';run.write_text(json.dumps({'plan':PLAN,'sessions':[],'ledger':[]}))
   (Path(d)/'usage.json').write_text(json.dumps({'ledger':[{'cost_status':'reserved','accounted_usd':.1,'cost_usd':None}]}))
   with patch.object(sys,'argv',['audience','report',str(run)]),patch.object(cli,'build_report',side_effect=lambda value,path:captured.append(value) or {}),contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(cli.main(),0)
   self.assertEqual(captured[0]['ledger'][0]['cost_status'],'unknown')
   self.assertEqual(captured[0]['ledger'][0]['accounted_usd'],.1)

 def test_offline_regeneration_accepts_forecast_without_paid_synthesis(self):
  captured=[]
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'run.json';run.write_text(json.dumps({'plan':PLAN,'sessions':[],'ledger':[]}))
   assumptions=Path(d)/'inputs.json';inputs={'source':'Explicit test assumptions','monthly_visitors':100,'paid_conversion':[.1,.2]};assumptions.write_text(json.dumps(inputs))
   with patch.object(sys,'argv',['audience','report',str(run),'--forecast-inputs',str(assumptions)]),patch.object(cli,'enrich_run') as paid,patch.object(cli,'build_report',side_effect=lambda value,path:captured.append(value) or {}),contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(cli.main(),0)
    paid.assert_not_called()
   self.assertEqual(captured[0]['forecast_inputs'],inputs)
   self.assertNotIn('forecast_inputs',json.loads(run.read_text()))

 def test_live_finalization_persists_synthesis_and_final_ledger(self):
  run={'plan':PLAN,'sessions':[]};client=FakeClient()
  def enrich(value,current):
   value['product_synthesis']={'status':'skipped','reason':'No sessions'}
   current.ledger=[{'cost_status':'actual','cost_usd':.001,'accounted_usd':.001}]
  with tempfile.TemporaryDirectory() as d,patch.object(cli,'enrich_run',side_effect=enrich) as synthesis,patch.object(cli,'build_report',return_value={}):
   cli.finish_report(run,client,Path(d))
   saved=json.loads((Path(d)/'run.json').read_text())
   synthesis.assert_called_once_with(run,client)
   self.assertEqual(saved['ledger'][0]['cost_usd'],.001)
   self.assertEqual(saved['product_synthesis']['status'],'skipped')

if __name__=='__main__':unittest.main()
