"""Real execution and lifecycle constraints, independent of model-reported success."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audience_core.engine import advance, clean_snapshot, new_run, validate_decision
from audience_core.openrouter import AudienceError

class Client:
    def __init__(self, reply): self.reply=reply; self.ledger=[]; self.calls=0
    def complete_json(self, *args, **kwargs): self.calls+=1; return self.reply

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.plan={'task':'Получить сравнение', 'url':'https://example.org', 'max_steps':8,
          'max_wait_s':20, 'personas':[{'id':'p1','model':'a/model','goal':'Сравнить варианты',
                                      'scenario_modes':['first_use','resume','regular']}]}
        self.catalogue=[{'id':'a/model'}]
        self.obs={'url':'https://example.org','title':'Assistant','text':'Задайте вопрос',
           'task_state':'idle','elements':[{'id':'prompt','role':'textbox','name':'Запрос'},
           {'id':'send','role':'button','name':'Отправить'},
           {'id':'new-chat','role':'link','name':'Новый чат'}]}
        self.run=new_run(self.plan)
    def finish(self, eid):
        return {'action':{'type':'finish'},'feedback':{'outcome':'success','summary':'Получен результат',
               'evidence_ids':[eid], 'assessment':{'satisfaction':5,'evidence_ids':[eid]}}}
    def send(self):
        client=Client({'action':{'type':'click','target':'send'}})
        advance(self.run,'p1-first_use',self.obs,client,self.catalogue)
        return client
    def test_pending_response_waits_without_spending_model_calls(self):
        client=self.send()
        obs={**self.obs,'text':'Ответ готовится','task_state':'running'}
        result=advance(self.run,'p1-first_use',obs,client,self.catalogue,{'status':'ok'})
        self.assertEqual(result['action'],{'type':'wait','seconds':10})
        self.assertEqual(client.calls,1)
        self.assertTrue(self.run['sessions'][0]['task_started'])
        self.assertFalse(self.run['sessions'][0]['task_completed'])
    def test_waiting_stops_at_response_limit_and_never_becomes_product_failure(self):
        client=self.send(); obs={**self.obs,'text':'Ответ готовится','task_state':'running'}
        for _ in range(3):
            result=advance(self.run,'p1-first_use',obs,client,self.catalogue,{'status':'ok'})
        self.assertEqual(result['status'],'time_limit')
        self.assertEqual(self.run['sessions'][0]['feedback'],{})
        self.assertEqual(client.calls,1)
    def test_complete_result_after_send_is_success_with_task_counts(self):
        client=self.send(); client.reply=self.finish('p1-first_use:e002')
        result=advance(self.run,'p1-first_use',{**self.obs,'text':'Сравнение: А лучше по цене, Б по сроку',
                       'task_state':'completed'},client,self.catalogue,{'status':'ok'})
        self.assertEqual(result['status'],'completed')
        self.assertTrue(self.run['sessions'][0]['task_started'])
        self.assertTrue(self.run['sessions'][0]['task_completed'])
    def test_new_chat_does_not_count_as_a_completed_task(self):
        client=Client({'action':{'type':'click','target':'new-chat'}})
        advance(self.run,'p1-first_use',self.obs,client,self.catalogue)
        client.reply=self.finish('p1-first_use:e002')
        result=advance(self.run,'p1-first_use',self.obs,client,self.catalogue,{'status':'ok'})
        self.assertEqual(result['status'],'error')
        self.assertFalse(self.run['sessions'][0]['task_started'])
        self.assertEqual(self.run['sessions'][0]['decision_audit'][-1]['raw']['feedback']['outcome'],'success')
    def test_draft_is_not_submission(self):
        client=Client({'action':{'type':'fill','target':'prompt','value':'Сравни варианты'}})
        advance(self.run,'p1-first_use',self.obs,client,self.catalogue)
        client.reply=self.finish('p1-first_use:e002')
        result=advance(self.run,'p1-first_use',self.obs,client,self.catalogue,{'status':'ok'})
        self.assertEqual(result['status'],'error')
        self.assertFalse(self.run['sessions'][0]['task_started'])
    def test_prior_task_may_complete_on_observe_only_resume_but_not_regular(self):
        client=self.send()
        busy={**self.obs,'text':'Ответ готовится','task_state':'running'}
        advance(self.run,'p1-first_use',busy,client,self.catalogue,{'status':'ok'})
        self.run['sessions'][0]['status']='time_limit'
        done={**self.obs,'text':'Готовое сравнение А и Б','task_state':'completed'}
        result=advance(self.run,'p1-resume',done,Client(self.finish('p1-resume:e001')),self.catalogue)
        self.assertEqual(result['status'],'completed')
        self.assertFalse(self.run['sessions'][1]['task_started'])
        result=advance(self.run,'p1-regular',done,Client(self.finish('p1-regular:e001')),self.catalogue)
        self.assertEqual(result['status'],'error')
    def test_existing_answer_expansion_does_not_create_new_task(self):
        old={**self.obs,'task_state':'completed','text':'Старый ответ','elements':
             [*self.obs['elements'],{'id':'expand','role':'button','name':'Показать всё'}]}
        client=Client({'action':{'type':'click','target':'expand'}})
        advance(self.run,'p1-first_use',old,client,self.catalogue)
        client.reply=self.finish('p1-first_use:e002')
        result=advance(self.run,'p1-first_use',old,client,self.catalogue,{'status':'ok'})
        self.assertEqual(result['status'],'error')
        self.assertFalse(self.run['sessions'][0]['task_started'])
    def test_success_must_cite_completed_result_not_running_spinner(self):
        client=self.send(); busy={**self.obs,'text':'Ответ готовится','task_state':'running'}
        advance(self.run,'p1-first_use',busy,client,self.catalogue,{'status':'ok'})
        client.reply=self.finish('p1-first_use:e002')
        result=advance(self.run,'p1-first_use',{**self.obs,'text':'Готовое сравнение','task_state':'completed'},
                       client,self.catalogue,{'status':'ok'})
        self.assertEqual(result['status'],'error')
    def test_wait_bounds_and_snapshot_state_are_validated(self):
        for value in (0,11,True,'10'):
            with self.subTest(value=value), self.assertRaises(AudienceError):
                validate_decision({'action':{'type':'wait','seconds':value}},self.obs,set())
        self.assertEqual(validate_decision({'action':{'type':'wait','seconds':3}},self.obs,set())['action']['seconds'],3)
        self.assertNotIn('task_state',clean_snapshot({**self.obs,'task_state':'made-up'}))
    def test_long_russian_plan_preserves_current_input_and_last_two_events(self):
        import json
        from audience_core.engine import model_messages
        persona=self.run['plan']['personas'][0]
        persona.update(goal='Сравнить варианты. '*100,selection_reason='Пояснение выбора аудитории. '*150,
          scenario_goals={'first_use':'Сравнить наушники для поездки в метро.','resume':'Вернуться к ответу. '*100},
          success_criteria=['Есть сравнение трёх моделей.','Есть итоговый выбор.'])
        self.run['plan']['task']='Проверить интерфейс и получить сравнение. '*80
        actual_value='Сравни наушники для метро по шумоподавлению и автономности.'
        obs=copy.deepcopy(self.obs)
        obs['text']='Большое описание продукта. '*300+'В поле введён запрос.'
        obs['elements'][0]['value']=actual_value
        session=self.run['sessions'][0]
        for n in range(6):
            session['events'].append({'id':f'p1-first_use:e{n:03d}',
              'action':{'type':'fill','target':'prompt','value':actual_value},
              'result':{'status':'ok','reason':'Запрос введён, кнопка отправки доступна.'},'observation':obs})
        messages=model_messages(self.run,session,clean_snapshot(obs))
        payload=json.loads(messages[1]['content'])
        self.assertLessEqual(len(json.dumps(messages,ensure_ascii=False).encode()),12000)
        self.assertEqual([e['id'] for e in payload['recent_events'][-2:]],['p1-first_use:e004','p1-first_use:e005'])
        self.assertEqual(payload['observation']['elements'][0]['value'],actual_value)
        self.assertEqual(payload['observation']['task_state'],'idle')
        self.assertNotIn('selection_reason',payload['persona'])
        self.assertNotIn('scenario_goals',payload['persona'])
    def test_safe_text_input_values_retained_but_credentials_omitted(self):
        token='sk-or-v1-'+'z'*40
        obs=clean_snapshot({**self.obs,'elements':[
          {'id':'q','role':'textbox','name':'Запрос','value':'Покажи варианты'},
          {'id':'key','role':'textbox','name':'API key','value':'private-value'},
          {'id':'login','role':'textbox','name':'Login','autocomplete':'username','value':'private-login'},
          {'id':'secret','role':'textbox','name':'Запрос','value':token},
          {'id':'pass','role':'textbox','input_type':'password','value':'password'}]})
        self.assertEqual(obs['elements'][0]['value'],'Покажи варианты')
        self.assertTrue(all('value' not in e for e in obs['elements'][1:]))
        self.assertNotIn('password',str(obs))

    def test_action_protocol_is_used_when_available(self):
        class ActionClient(Client):
            def complete_action(self,*args,**kwargs): self.calls+=1; return {'action':{'type':'fill','target':'prompt','value':'Тест'}}
            def complete_json(self,*args,**kwargs): raise AssertionError('strict planner parser used for action')
        result=advance(self.run,'p1-first_use',self.obs,ActionClient({}),self.catalogue)
        self.assertEqual(result['action']['type'],'fill')
    def test_invalid_model_feedback_is_retained_and_redacted(self):
        token='sk-or-v1-'+'z'*40
        result=advance(self.run,'p1-first_use',self.obs,Client({'action':{'type':'finish'},'feedback':{'summary':token}}),self.catalogue)
        self.assertEqual(result['status'],'error')
        self.assertNotIn(token,str(self.run['sessions'][0]['decision_audit']))
        self.assertIn('[REDACTED]',str(self.run['sessions'][0]['decision_audit']))

if __name__=='__main__': unittest.main()
