"""Multi-persona coverage must not turn visits into new product tasks."""
import unittest

from test_analysis import visit, run_for, analysis
from test_report_view import specimen
from audience_core.report import _aggregate
from audience_core.report_view import render_html


class MultiagentReportTests(unittest.TestCase):
    def test_resume_is_separate_from_new_repeat_task(self):
        first = visit('first', 'p1')
        first.update(task_started=True, task_completed=True)
        resumed = visit('resume', 'p1', 'resume')
        resumed.update(task_started=False, task_completed=False)
        regular = visit('regular', 'p1', 'regular', status='error')
        regular.update(task_started=False, task_completed=False)
        regular['events'][0]['observation']['task_state'] = 'idle'
        result = analysis(run_for([first, resumed, regular], agents=1))
        group, exp = result['audience'][0], result['experiment']
        self.assertEqual(group['resume']['n'], 1)
        self.assertEqual(group['repeat']['n'], 0)
        self.assertEqual(exp['tasks_started'], 1)
        self.assertEqual(exp['tasks_completed'], 1)
        self.assertEqual(exp['resume_sessions'], 1)
        self.assertEqual(exp['tasks_unknown'], 0)

    def test_uninstrumented_standalone_visit_has_unknown_task_count(self):
        uninstrumented = visit('standalone', 'p1')
        uninstrumented.update(task_started=False, task_completed=False)
        result = analysis(run_for([uninstrumented], agents=1))['experiment']
        self.assertEqual(result['tasks_started'], 0)
        self.assertEqual(result['tasks_unknown'], 1)
        self.assertEqual(result['executed_sessions'], 1)
        uninstrumented['events'][0]['observation']['task_state'] = 'idle'
        result = analysis(run_for([uninstrumented], agents=1))['experiment']
        self.assertEqual(result['tasks_unknown'], 0)

    def test_shared_account_disclosure_and_actual_unique_agents(self):
        first = visit('first', 'p1')
        repeat = visit('again', 'p1', 'regular')
        waiting = visit('pending', 'p2', status='pending')
        waiting['events'] = []
        run = run_for([first, repeat, waiting], agents=2)
        run['plan']['session_mode'] = 'shared_account'
        result = analysis(run)
        self.assertEqual(result['experiment']['planned_agents'], 2)
        self.assertEqual(result['experiment']['executed_agents'], 1)
        self.assertEqual(result['experiment']['executed_sessions'], 2)
        self.assertEqual(result['experiment']['tasks_unknown'], 2)
        self.assertIn('Общий тестовый аккаунт', result['experiment']['session_mode_note'])
        self.assertIn('Память и настройки аккаунта на сервере', result['experiment']['session_mode_note'])

    def test_no_priorities_does_not_promise_release_decisions(self):
        run, sessions, report = specimen(count=1)
        sessions[0]['feedback']['recommendations'] = []
        report.update(analysis(run))
        page = render_html(run, sessions, report)
        self.assertIn('<h1>Что удалось<br>проверить<br>в продукте.</h1>', page)
        self.assertNotIn('От наблюдений — к конкретным решениям.', page)
        self.assertNotIn('Этот тест показывает, где продукт мешает', page)
        self.assertIn('Следующий шаг исследования', page)

    def test_html_separates_visits_tasks_and_isolation(self):
        run, sessions, report = specimen(count=1)
        run['plan']['session_mode'] = 'shared_account'
        sessions[0]['task_started'] = True
        sessions[0]['task_completed'] = True
        report.update(analysis(run))
        page = render_html(run, sessions, report)
        self.assertIn('Подтверждённо запущено новых задач: 1', page)
        self.assertIn('Продолжение прежней задачи</th>', page)
        self.assertIn('Общий тестовый аккаунт', page)

    def test_deadline_is_not_failed_product_result(self):
        timed = visit('timed', 'p1', status='time_limit')
        metrics = _aggregate([timed])
        self.assertEqual(metrics['time_limited'], 1)
        self.assertEqual(metrics['eligible'], 0)
        self.assertEqual(metrics['task_non_success'], 0)


if __name__ == '__main__':
    unittest.main()
