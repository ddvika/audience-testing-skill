"""Host runtime integration: one browser, separate personas, one cap and deadline."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import audience as cli

PLAN={'url':'https://fixture.example','task':'Get a result','budget_usd':2,'max_steps':6,
      'models':[{'id':'test/model','count':2}], 'personas':[
          {'id':'p1','name':'One','goal':'Question one','model':'test/model','scenario_modes':['first_use','resume']},
          {'id':'p2','name':'Two','goal':'Question two','model':'test/model','scenario_modes':['first_use']}]}
SNAPSHOT={'url':'https://fixture.example','title':'Product','text':'Ask a question','elements':[], 'task_state':'idle'}

class Client:
    paths=[]
    def __init__(self,*args,**kwargs):
        self.ledger=[{'cost_status':'actual','accounted_usd':.03,'cost_usd':.03}]
        self.spent_usd=.03;self.response_diagnostics=[];self.paths.append(kwargs.get('ledger_path'))
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def set_deadline(self,value):self.deadline=value
    def list_models(self):return [{'id':'test/model'}]

class MultiRuntime(unittest.TestCase):
    def args(self,path,**kw):
        return SimpleNamespace(**{'output':str(path),'budget':2,'snapshot':None,'forecast_inputs':None,
            'session_mode':'shared_account','max_minutes':30,'max_wait_seconds':180,'ledger_path':None,'resume':False,**kw})
    def run_host(self,path,commands,**kw):
        args=self.args(path,**kw)
        with patch.object(cli,'OpenRouterClient',Client),patch.object(cli,'key_for',return_value='fixture'),\
             patch.object(cli,'plan_for',side_effect=lambda *a:copy.deepcopy(PLAN)),\
             patch.object(cli,'enrich_run'),patch.object(cli,'build_report',return_value={}),\
             patch.object(sys,'stdin',io.StringIO('\n'.join(json.dumps(c) for c in commands)+'\n')),\
             contextlib.redirect_stdout(io.StringIO()) as stream:
            cli.host(args)
        return [json.loads(s) for s in stream.getvalue().splitlines()],json.loads((Path(path)/'run.json').read_text())

    def test_shared_account_requires_preparation_without_paid_action(self):
        with tempfile.TemporaryDirectory() as d,patch.object(cli,'advance') as advance:
            rows,run=self.run_host(d,[{'session_id':'p1-first_use','snapshot':SNAPSHOT},{'command':'quit'}])
            advance.assert_not_called()
            self.assertIn('session_context',rows[1]['error'])
            self.assertTrue(rows[0]['next_session']['session_context_required'])
            self.assertEqual(run['plan']['session_mode'],'shared_account')
            self.assertIn('память',run['warnings'][0])

    def test_two_personas_get_separate_chats_and_can_run_sequentially(self):
        seen=[]
        def decision(run,sid,snapshot,client,catalogue,result):
            session=cli.session_for(run,sid);seen.append((sid,session['session_context'].copy()))
            session['status']='completed';session['events']=[{'id':sid+':e001'}]
            return {'session_id':sid,'status':'completed'}
        commands=[{'session_id':sid,'snapshot':SNAPSHOT,'session_context':{'kind':'new_chat','url':SNAPSHOT['url']}}
                  for sid in ('p1-first_use','p2-first_use')]+[{'command':'quit'}]
        with tempfile.TemporaryDirectory() as d,patch.object(cli,'advance',side_effect=decision):
            rows,run=self.run_host(d,commands)
            self.assertEqual([s[0] for s in seen],['p1-first_use','p2-first_use'])
            self.assertEqual({s[1]['model_history_scope'] for s in seen},{'p1','p2'})
            self.assertEqual(sum(s['status']=='completed' for s in run['sessions']),2)
            self.assertEqual(run['runtime']['starting_accounted_usd'],.03)

    def test_shared_browser_cannot_switch_a_running_persona(self):
        run=cli.new_run(copy.deepcopy(PLAN));run['plan']['session_mode']='shared_account'
        run['sessions'][0]['status']='running'
        with self.assertRaisesRegex(cli.AudienceError,'busy'):
            cli.prepare_session(run,run['sessions'][2],{'snapshot':SNAPSHOT,'session_context':{'kind':'new_chat','url':SNAPSHOT['url']}})

    def test_new_chat_cannot_reuse_a_completed_response(self):
        run=cli.new_run(copy.deepcopy(PLAN));run['plan']['session_mode']='shared_account'
        with self.assertRaisesRegex(cli.AudienceError,'prior task'):
            cli.prepare_session(run,run['sessions'][0],{'snapshot':{**SNAPSHOT,'task_state':'completed'},'session_context':{'kind':'new_chat','url':SNAPSHOT['url']}})

    def test_resume_requires_that_personas_own_submitted_task(self):
        run=cli.new_run(copy.deepcopy(PLAN));run['plan']['session_mode']='shared_account'
        run['sessions'][2]['task_started']=True
        message={'snapshot':SNAPSHOT,'session_context':{'kind':'resume_previous_task','url':SNAPSHOT['url']}}
        with self.assertRaisesRegex(cli.AudienceError,'No submitted task'):
            cli.prepare_session(run,run['sessions'][1],message)
        run['sessions'][0].update(task_started=True,conversation_url=SNAPSHOT['url'])
        cli.prepare_session(run,run['sessions'][1],message)
        self.assertEqual(run['sessions'][1]['session_context']['model_history_scope'],'p1')

    def test_resume_rejects_another_personas_chat(self):
        run=cli.new_run(copy.deepcopy(PLAN));run['plan']['session_mode']='shared_account'
        run['sessions'][0].update(task_started=True,conversation_url='https://fixture.example/chat/one')
        run['sessions'][2].update(task_started=True,conversation_url='https://fixture.example/chat/two')
        wrong='https://fixture.example/chat/two'
        with self.assertRaisesRegex(cli.AudienceError,'recorded task conversation URL'):
            cli.prepare_session(run,run['sessions'][1],{'snapshot':{**SNAPSHOT,'url':wrong},
                'session_context':{'kind':'resume_previous_task','url':wrong}})
        self.assertNotIn('session_context',run['sessions'][1])

    def test_hint_uses_prior_submitted_task_not_future_or_observation_visit(self):
        run=cli.new_run(copy.deepcopy(PLAN));run['plan']['session_mode']='shared_account'
        run['sessions'][0].update(task_started=True,conversation_url='https://fixture.example/chat/one')
        observed={'id':'p1-observation','persona_id':'p1','mode':'resume','model':'test/model','status':'completed',
                  'events':[{'id':'observation'}],'conversation_url':'https://fixture.example/other','task_started':False}
        run['sessions'].insert(1,observed)
        run['sessions'].append({'id':'p1-regular','persona_id':'p1','task_started':True,'conversation_url':'https://fixture.example/chat/future'})
        hint=cli.session_hint(run,run['sessions'][2])
        self.assertEqual(hint['previous_conversation_url'],'https://fixture.example/chat/one')

    def test_external_ledger_reused_and_written_to_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            ledger=Path(d)/'earlier-run'/'usage.json'
            _,run=self.run_host(Path(d)/'new-run',[{'command':'quit'}],ledger_path=str(ledger))
            self.assertEqual(Client.paths[-1],ledger)
            self.assertEqual(run['runtime']['ledger_path'],str(ledger))
            self.assertEqual(run['ledger'][0]['cost_usd'],.03)

    def test_deadline_preserves_unconfirmed_action_and_skips_synthesis(self):
        run=cli.new_run(copy.deepcopy(PLAN));run['runtime']={'deadline_unix':time.time()-1}
        run['sessions'][0].update(status='running',pending_action={'type':'click','target':'send'})
        with tempfile.TemporaryDirectory() as d,patch.object(cli,'enrich_run') as enrich,patch.object(cli,'build_report',return_value={}):
            cli.finish_report(run,Client(),Path(d))
            enrich.assert_not_called()
            self.assertTrue(all(s['status']=='time_limit' for s in run['sessions']))
            self.assertEqual(run['sessions'][0]['unconfirmed_action']['target'],'send')
            self.assertNotIn('pending_action',run['sessions'][0])

    def test_resume_does_not_replan_reset_cap_or_deadline(self):
        with tempfile.TemporaryDirectory() as d:
            _,original=self.run_host(d,[{'command':'quit'}])
            with patch.object(cli,'plan_for') as plan:
                # Direct invocation so run_host's planning patch does not mask this check.
                with patch.object(cli,'OpenRouterClient',Client),patch.object(cli,'key_for',return_value='fixture'),patch.object(cli,'enrich_run'),patch.object(cli,'build_report',return_value={}),patch.object(sys,'stdin',io.StringIO('{"command":"quit"}\n')),contextlib.redirect_stdout(io.StringIO()):
                    cli.host(self.args(d,resume=True))
                plan.assert_not_called()
            resumed=json.loads((Path(d)/'run.json').read_text())
            self.assertEqual(resumed['runtime']['deadline_unix'],original['runtime']['deadline_unix'])
            with self.assertRaisesRegex(cli.AudienceError,'original budget'):
                cli.host(self.args(d,resume=True,budget=3))

    def test_explicit_retry_preserves_events_counts_budget_and_deadline(self):
        run=cli.new_run(copy.deepcopy(PLAN));run['runtime']={'deadline_unix':time.time()+60}
        run['ledger']=[{'accounted_usd':.15}]
        session=run['sessions'][0]
        session.update(status='error',error='Invalid completion',decisions=1,events=[{'id':'p1:e1'}],feedback={'validation_error':'bad'})
        before=copy.deepcopy(run)
        cli.retry_session(run,session)
        self.assertEqual(session['status'],'running')
        self.assertEqual(session['decisions'],1);self.assertEqual(session['events'],before['sessions'][0]['events'])
        self.assertEqual(run['ledger'],before['ledger']);self.assertEqual(run['runtime'],before['runtime'])
        self.assertEqual(session['retry_history'][0]['previous_error'],'Invalid completion')
        self.assertEqual(session['retry_history'][0]['previous_feedback'],{'validation_error':'bad'})
        self.assertNotIn('pending_action',session)

    def test_retry_is_bounded_and_never_replays_pending_actions(self):
        run=cli.new_run(copy.deepcopy(PLAN));session=run['sessions'][0]
        with self.assertRaisesRegex(cli.AudienceError,'Only an error'):cli.retry_session(run,session)
        session.update(status='error',decisions=1,pending_action={'type':'click','target':'send'})
        with self.assertRaisesRegex(cli.AudienceError,'pending or unconfirmed'):cli.retry_session(run,session)
        session.pop('pending_action')
        for _ in range(2):
            session['status']='error';cli.retry_session(run,session)
        session['status']='error'
        with self.assertRaisesRegex(cli.AudienceError,'two explicit retries'):cli.retry_session(run,session)
        self.assertEqual(session['decisions'],1)

    def test_resumed_diagnostics_preserve_prior_raw_records_without_duplicates(self):
        run=cli.new_run(copy.deepcopy(PLAN));first=Client();second=Client()
        old={'sequence':3,'model':'test/a','raw_content':'old raw answer'}
        new={'sequence':4,'model':'test/b','raw_content':'new raw answer'}
        first.response_diagnostics=[old]
        second.response_diagnostics=[old,new]
        with tempfile.TemporaryDirectory() as d:
            cli.checkpoint(run,first,Path(d))
            cli.checkpoint(run,second,Path(d))
            cli.checkpoint(run,second,Path(d))
            self.assertEqual(json.loads((Path(d)/'action-responses.json').read_text()),[old,new])

    def test_diagnostics_are_separate_from_run_and_report(self):
        run=cli.new_run(copy.deepcopy(PLAN));client=Client()
        client.response_diagnostics=[{'raw':'one action then discarded action'}]
        with tempfile.TemporaryDirectory() as d:
            cli.checkpoint(run,client,Path(d))
            self.assertTrue((Path(d)/'action-responses.json').exists())
            self.assertNotIn('response_diagnostics',json.loads((Path(d)/'run.json').read_text()))

if __name__=='__main__':unittest.main()
