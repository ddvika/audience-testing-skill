"""Host transcript intake preserves literal evidence, not invented chat history."""
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audience as cli
from audience_core.engine import record_transcript, clean_snapshot
from audience_core.openrouter import AudienceError


def fixture():
    events = [
        {'id':'p1-first_use:e001','action':{'type':'fill','target':'prompt','value':'Which plan fits a team?'},
         'observation':{'url':'https://fixture.example/chat/one','title':'Help','text':'Which plan fits a team?','task_state':'idle','elements':[]},'result':{'status':'ok'}},
        {'id':'p1-first_use:e002','action':{'type':'click','target':'send'},
         'observation':{'url':'https://fixture.example/chat/one','title':'Help','text':'Working on your question','task_state':'running','elements':[]},'result':{'status':'ok'}},
        {'id':'p1-first_use:e003','action':{'type':'wait','seconds':1},
         'observation':{'url':'https://fixture.example/chat/one','title':'Help','text':'Team plan.\nYou can add five members.','task_state':'completed','elements':[]},'result':{'status':'ok'}},
    ]
    run={'id':'fixture','created_at':'2026-11-09T00:00:00Z','plan':{'url':'https://fixture.example','task':'Choose a team plan',
         'max_steps':8,'budget_usd':1,'session_mode':'isolated','models':[{'id':'fixture/model','count':1}],
         'personas':[{'id':'p1','name':'Team buyer','goal':'Choose a plan','model':'fixture/model','scenario_modes':['first_use']}]},
         'sessions':[{'id':'p1-first_use','persona_id':'p1','model':'fixture/model','mode':'first_use','status':'completed',
                      'events':events,'feedback':{'outcome':'success','summary':'Plan found','evidence_ids':['p1-first_use:e003']},
                      'task_started':True,'task_completed':True,'duration_s':4}],
         'ledger':[],'warnings':[],'runtime':{'deadline_unix':time.time()+60}}
    transcript={'source':'captured_browser_text','capture_status':'complete','product_name':'Fixture',
                'capture_note':'Literal saved text. This is not a server export.',
                'messages':[
                    {'role':'user','text':'Which plan fits a team?','event_ids':['p1-first_use:e001','p1-first_use:e002'],'submission_event_id':'p1-first_use:e002'},
                    {'role':'assistant','text':'Team plan.\nYou can add five members.','event_ids':['p1-first_use:e003']}]}
    return run, transcript


class TranscriptTests(unittest.TestCase):
    def test_exact_capture_is_idempotent_and_keeps_source_events(self):
        run,value=fixture();events=copy.deepcopy(run['sessions'][0]['events'])
        first=record_transcript(run,'p1-first_use',value)
        saved=copy.deepcopy(run['sessions'][0])
        second=record_transcript(run,'p1-first_use',value)
        self.assertTrue(first['changed']);self.assertFalse(second['changed'])
        self.assertEqual(saved,run['sessions'][0]);self.assertEqual(events,saved['events'])
        self.assertEqual(saved['transcript']['messages'][1]['text'],value['messages'][1]['text'])
        self.assertEqual(saved['transcript']['capture_status'],'complete')

    def test_replacement_retains_prior_capture_in_audit(self):
        run,value=fixture();record_transcript(run,'p1-first_use',value)
        prior=copy.deepcopy(run['sessions'][0]['transcript'])
        value['capture_note']='Reviewed literal source boundaries.'
        record_transcript(run,'p1-first_use',value)
        self.assertEqual(run['sessions'][0]['transcript_revisions'][0]['previous'],prior)

    def test_rejects_summaries_cross_persona_evidence_and_secrets(self):
        for change in ('invented','cross_persona','secret','wrong_role','unknown_field'):
            run,value=fixture()
            if change=='invented':value['messages'][1]['text']='The answer says buy the expensive plan.'
            if change=='cross_persona':value['messages'][1]['event_ids']=['p2-first_use:e003']
            if change=='secret':value['messages'][1]['text']='sk-or-v1-'+'x'*32
            if change=='wrong_role':value['messages'][1]['role']='system'
            if change=='unknown_field':value['code']='execute me'
            with self.subTest(change=change),self.assertRaises(AudienceError):record_transcript(run,'p1-first_use',value)
            self.assertNotIn('transcript',run['sessions'][0])

    def test_drafts_and_unsent_followups_are_rejected(self):
        run,value=fixture();run['sessions'][0]['task_started']=False
        with self.assertRaisesRegex(AudienceError,'submitted task'):record_transcript(run,'p1-first_use',value)
        run,value=fixture();value['messages'][0]['submission_event_id']='p1-first_use:e001'
        with self.assertRaisesRegex(AudienceError,'observed click'):record_transcript(run,'p1-first_use',value)
        run,value=fixture();run['sessions'][0]['events'][1]['observation']['task_state']='idle'
        with self.assertRaisesRegex(AudienceError,'observed click'):record_transcript(run,'p1-first_use',value)

    def test_multiturn_uses_new_submission_and_order(self):
        run,value=fixture();s=run['sessions'][0]
        for index,action,text,state in [(4,{'type':'fill','target':'prompt','value':'Can I cancel?'},'Can I cancel?','completed'),
                                         (5,{'type':'click','target':'send'},'Working','running'),
                                         (6,{'type':'wait','seconds':1},'Cancel in settings.','completed')]:
            s['events'].append({'id':f'p1-first_use:e{index:03d}','action':action,'result':{'status':'ok'},
                'observation':{'text':text,'task_state':state}})
        value['messages'] += [{'role':'user','text':'Can I cancel?','event_ids':['p1-first_use:e004','p1-first_use:e005'],'submission_event_id':'p1-first_use:e005'},
                              {'role':'assistant','text':'Cancel in settings.','event_ids':['p1-first_use:e006']}]
        record_transcript(run,'p1-first_use',value)
        self.assertEqual(len(s['transcript']['messages']),4)
        value['messages']=list(reversed(value['messages']))
        with self.assertRaisesRegex(AudienceError,'chronological'):record_transcript(run,'p1-first_use',value)

    def test_clipped_observation_is_flagged_and_capture_marked_partial(self):
        snap=clean_snapshot({'url':'https://fixture.example','text':'x'*11000,'elements':[]})
        self.assertEqual(len(snap['text']),10000);self.assertTrue(snap['text_truncated'])
        run,value=fixture();run['sessions'][0]['events'][2]['observation']['text_truncated']=True
        record_transcript(run,'p1-first_use',value)
        self.assertEqual(run['sessions'][0]['transcript']['capture_status'],'partial')
        self.assertIn('truncated',run['sessions'][0]['transcript']['capture_note'])

    def test_host_command_round_trip_to_report_without_paid_calls(self):
        class Client:
            def __init__(self,*args,**kwargs):self.ledger=[];self.spent_usd=0;self.response_diagnostics=[]
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def set_deadline(self,*args):pass
            def list_models(self):return [{'id':'fixture/model'}]
            def complete_json(self,*args,**kwargs):raise AssertionError('Transcript must not make a model call')
        run,value=fixture()
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d);(directory/'run.json').write_text(json.dumps(run))
            args=SimpleNamespace(output=d,budget=1,session_mode='isolated',resume=True,ledger_path=None,
                max_minutes=30,max_wait_seconds=180,forecast_inputs=None)
            commands=[{'command':'transcript','session_id':'p1-first_use','transcript':value},{'command':'quit'}]
            with patch.object(cli,'OpenRouterClient',Client),patch.object(cli,'key_for',return_value='fixture'),\
                 patch.object(cli,'enrich_run'),patch.object(sys,'stdin',io.StringIO('\n'.join(json.dumps(c) for c in commands)+'\n')),\
                 contextlib.redirect_stdout(io.StringIO()) as stream:
                cli.host(args)
            output=[json.loads(line) for line in stream.getvalue().splitlines()]
            self.assertTrue(output[1]['transcript_saved']);self.assertEqual(output[1]['message_count'],2)
            saved=json.loads((directory/'run.json').read_text())
            exported=json.loads((directory/'report.json').read_text())
            self.assertEqual(saved['sessions'][0]['transcript'],exported['run']['sessions'][0]['transcript'])
            html=(directory/'report.html').read_text()
            self.assertIn('Which plan fits a team?',html);self.assertIn('Team plan.\nYou can add five members.',html)
            self.assertIn('id="dialogues"',html)


if __name__=='__main__':unittest.main()
