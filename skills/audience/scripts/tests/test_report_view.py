"""Report UI regressions: honest sparse states, provenance, scale and escaping."""
import copy
import json
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audience_core.report_view import render_html
from audience_core.report import _aggregate, _forecast
from audience_core.forecast import extend_forecast
from audience_core.analysis import analyze


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__();self.ids=[];self.hrefs=[];self.scripts=[];self.external=[];self.feed(source)

    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if a.get('href','').startswith('#'):self.hrefs.append(a['href'][1:])
        if tag=='script':self.scripts.append(a)
        if tag in {'script','img','link','iframe'} and (a.get('src') or a.get('href')):self.external.append(a)


def specimen(status='completed', count=2):
    personas=[];sessions=[]
    for index in range(count):
        pid='p'+str(index);sid=pid+'-first';eid=sid+':e1'
        personas.append({'id':pid,'name':'AI агент '+str(index),'segment':'Выбрать услугу','group_id':'g1','goal':'Найти свободное время и проверить условия записи','model':'fixture/model','device':'desktop','scenario_modes':['first_use']})
        sessions.append({'id':sid,'persona_id':pid,'mode':'first_use','model':'fixture/model','status':status,'events':[] if status=='pending' else [{'id':eid,'action':{'type':'click','target':'times'},'observation':{'title':'Расписание','url':'https://example.test/schedule','text':'Свободные окна показаны','viewport':{'width':1280,'height':900}},'result':{'status':'ok'}}], 'feedback':{} if status in {'pending','blocked'} else {'outcome':'success','rating':8,'return_intent':True,'summary':'Время выбрано.','evidence_ids':[eid],'assessment':{'satisfaction':4,'effort':2,'purpose_clear':True,'next_step_clear':True,'result_clear':False,'evidence_ids':[eid]},'likes':['Расписание легко сравнить'],'recommendations':[{'change':'Показывать, подтверждена ли запись','reason':'Статус записи неочевиден','observed':'После выбора времени непонятно, создана ли запись','proposed':'Показать итог и кнопку подтверждения','issue_key':'confirmation','stage':'result','scope':'flow','expected_metric':'Доля агентов, понявших результат','how_to_verify':'Повторить сценарий выбора времени','evidence_ids':[eid]}]}})
    run={'synthetic_fixture':True,'plan':{'url':'https://example.test','task':'Проверить запись на услугу','product_summary':'Онлайн-запись на услуги','personas':personas,'scenario_modes':['first_use']},'sessions':sessions}
    metrics=_aggregate(sessions);report={'metrics':metrics,'forecast':_forecast({}),'costs':{}}
    report.update(analyze(run,sessions,metrics));return run,sessions,report


class ViewTests(unittest.TestCase):
    def test_sections_no_external_resources_and_valid_anchors(self):
        page=render_html(*specimen());parsed=Page(page)
        for section in ['experiment','decisions','priorities','audience','ux','satisfaction','forecast','plan','evidence']:
            self.assertIn(section,parsed.ids)
        self.assertEqual(len(parsed.ids),len(set(parsed.ids)))
        self.assertFalse(set(parsed.hrefs)-set(parsed.ids))
        self.assertEqual(parsed.external,[])
        self.assertEqual(len(parsed.scripts),2)
        self.assertIn('Дизайн эксперимента',page)
        self.assertIn('#fff4e6',page)
        self.assertIn('#cf1747',page)
        self.assertLess(len(page.encode()),150000)

    def test_pending_and_blocked_are_not_failed_product_experience(self):
        for status in ['pending','blocked']:
            page=render_html(*specimen(status=status))
            self.assertIn('Что удалось<br>проверить',page)
            self.assertNotIn('AI-агентов прошли продукт',page)
            self.assertIn('Доступных оценок результата пока нет',page)
            self.assertIn('Подтверждённых приоритетов пока нет',page)

    def test_hostile_text_cannot_add_script_or_url(self):
        run,sessions,report=specimen()
        bad='</script><script>alert(1)</script><img src=x onerror=alert(2)>'
        report['insight']=bad;run['plan']['url']='javascript:alert(3)'
        report['experiment']['url']='javascript:alert(3)'
        report['audience'][0]['personas'][0]['name']=bad
        page=render_html(run,sessions,report);parsed=Page(page)
        self.assertEqual(len(parsed.scripts),2)
        self.assertFalse(parsed.external)
        self.assertNotIn('href="javascript:',page)
        self.assertIn('\\u003c/script\\u003e',page)

    def test_named_forecast_has_computed_values_and_no_synthetic_uplift(self):
        run,sessions,report=specimen()
        inputs={'source':'Авторские условия','monthly_visitors':1000,'baseline':{'registration_rate':.4,'activation_rate':.5},'scenarios':[{'name':'one','label':'Первый','assumptions':{'registration_rate':.5,'activation_rate':.5}},{'name':'two','label':'Второй','assumptions':{'registration_rate':.5,'activation_rate':.6}}]}
        report['forecast']=extend_forecast(inputs,_forecast({}))
        page=render_html(run,sessions,report)
        self.assertIn('data-forecast="0"',page);self.assertIn('data-forecast="1"',page)
        self.assertIn('id="forecast-delta">+50',page)
        self.assertIn('id="forecast-percent">25%',page)
        self.assertNotIn('Для расчёта нужны исходные данные</div><h3>',page)

    def test_many_personas_have_bounded_visual_map_and_roster(self):
        page=render_html(*specimen(status='pending',count=1000))
        self.assertEqual(page.count('class="hero-agent '),120)
        self.assertEqual(page.count('class="person-record"'),60)
        self.assertLess(len(page.encode()),1500000)
        payload=json.loads(re.search(r'<script type="application/json" id="report-data">(.*?)</script>',page,re.S).group(1))
        self.assertEqual(len(payload['people']),1000)


if __name__=='__main__':unittest.main()
