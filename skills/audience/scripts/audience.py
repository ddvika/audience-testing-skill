#!/usr/bin/env python3
"""Audience CLI: host-browser bridge and optional standalone browser runner."""
from __future__ import annotations
import argparse
import asyncio
import getpass
import json
import os
import math
import select
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parent))
from audience_core.openrouter import OpenRouterClient, AudienceError, BudgetExceeded
from audience_core.planner import create_plan
from audience_core.engine import new_run, advance, write_json, redact, session_for, clean_snapshot, record_transcript
from audience_core.report import build_report
from audience_core.synthesis import enrich_run


def emit(value):
    print(json.dumps(redact(value),ensure_ascii=False),flush=True)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def key_for(args):
    key=os.environ.get('OPENROUTER_API_KEY')
    if not key and getattr(args,'prompt_key',False):
        if not sys.stdin.isatty():raise AudienceError('Use OPENROUTER_API_KEY in non-interactive environments.')
        key=getpass.getpass('OpenRouter key (hidden; kept in process memory): ')
    if not key:raise AudienceError('Set OPENROUTER_API_KEY or use --prompt-key in a terminal.')
    return key


def plan_for(args, client, snapshot=None):
    plan=create_plan(client,args.url,redact(args.task),audience=redact(args.audience),
        agents=None if args.agents=='auto' else int(args.agents),
        models=args.models.split(',') if args.models else None,budget_usd=args.budget,
        snapshot=redact(snapshot),max_steps=args.max_steps,
        scenarios=args.scenarios.split(',') if args.scenarios else None)
    if args.device!='auto':
        for persona in plan['personas']:persona['device']=args.device
        plan.setdefault('warnings',[]).append('Device explicitly fixed to '+args.device)
    plan['session_mode']=getattr(args,'session_mode','isolated')
    plan['max_wait_s']=getattr(args,'max_wait_seconds',180)
    return plan


ACTIVE_STATUSES={'pending','running'}
SHARED_WARNING=('Агенты работают в одном тестовом аккаунте, в отдельных чатах и с отдельной историей модели. '
                'История, память и лимиты продукта на стороне сервера могут быть общими; это не независимые новые аккаунты.')


def ledger_for(args,directory):
    path=Path(getattr(args,'ledger_path',None) or directory/'usage.json').expanduser().resolve()
    path.parent.mkdir(parents=True,exist_ok=True)
    return path


def runtime_start(args,client,run=None):
    now=time.time()
    runtime=(run or {}).get('runtime',{})
    deadline=runtime.get('deadline_unix',now+getattr(args,'max_minutes',30)*60)
    remaining=max(0,deadline-now)
    if hasattr(client,'set_deadline'):client.set_deadline(time.monotonic()+remaining)
    return {**runtime,'started_unix':runtime.get('started_unix',now),'deadline_unix':deadline,
            'max_minutes':getattr(args,'max_minutes',30),'session_mode':getattr(args,'session_mode','isolated'),
            'starting_accounted_usd':runtime.get('starting_accounted_usd',float(client.spent_usd)),
            'starting_ledger_entries':runtime.get('starting_ledger_entries',len(client.ledger))}


def attach_runtime(run,args,runtime,ledger_path):
    mode=getattr(args,'session_mode','isolated')
    run['plan']['session_mode']=mode
    run['plan']['max_wait_s']=getattr(args,'max_wait_seconds',180)
    run['runtime']={**runtime,'session_mode':mode,'ledger_path':str(ledger_path),
                    'persona_model_histories':'separate','browser_execution':'sequential' if mode=='shared_account' else 'isolated_contexts'}
    if mode=='shared_account' and SHARED_WARNING not in run.setdefault('warnings',[]):run['warnings'].append(SHARED_WARNING)


def deadline_expired(run):
    deadline=run.get('runtime',{}).get('deadline_unix')
    return deadline is not None and time.time()>=deadline


def stop_at_deadline(run):
    if not deadline_expired(run):return False
    for session in run['sessions']:
        if session['status'] in ACTIVE_STATUSES:
            session['status']='time_limit';session['stop_reason']='Общий лимит времени исследования исчерпан.'
            if session.get('pending_action'):session['unconfirmed_action']=session.pop('pending_action')
    run.setdefault('runtime',{})['stop_reason']='time_limit'
    return True


def prior_task_session(run,session):
    earlier=[]
    for candidate in run['sessions']:
        if candidate['id']==session['id']:break
        if candidate['persona_id']==session['persona_id'] and candidate.get('task_started'):
            earlier.append(candidate)
    return earlier[-1] if earlier else None


def session_hint(run,session=None):
    if session is None:
        session=next((s for s in run['sessions'] if s['status']=='running'),None)
        session=session or next((s for s in run['sessions'] if s['status']=='pending'),None)
    if session is None:return None
    persona=next(p for p in run['plan']['personas'] if p['id']==session['persona_id'])
    previous_task=prior_task_session(run,session)
    return {'id':session['id'],'persona_id':session['persona_id'],'name':persona.get('name',persona['id']),
            'mode':session['mode'],'model':session['model'],'status':session['status'],
            'goal':persona.get('scenario_goals',{}).get(session['mode'],persona.get('goal','')),
            'prepare':'resume_previous_task' if session['mode']=='resume' else 'new_chat_or_fresh_journey',
            'previous_conversation_url':previous_task.get('conversation_url') if previous_task else None,
            'session_context_required':run['plan'].get('session_mode')=='shared_account' and not session.get('session_context')}


def prepare_session(run,session,message):
    if run['plan'].get('session_mode')!='shared_account':return
    conflicting=next((s for s in run['sessions'] if s['id']!=session['id'] and s['status']=='running'),None)
    if conflicting:raise AudienceError('Shared browser is busy: finish or stop '+conflicting['id']+' before switching personas.')
    if session.get('session_context'):return
    context=message.get('session_context')
    if not isinstance(context,dict):raise AudienceError('Shared-account first observation needs session_context with kind and observed url; prepare a separate chat/journey for this persona.')
    kind=context.get('kind')
    permitted={'resume_previous_task'} if session['mode']=='resume' else {'new_chat','fresh_journey'}
    if kind not in permitted:raise AudienceError('Session context does not match this visit: '+', '.join(sorted(permitted)))
    snapshot=message.get('snapshot',{})
    if context.get('url')!=snapshot.get('url'):raise AudienceError('Session context URL must match the actual current snapshot.')
    if kind=='new_chat' and snapshot.get('task_state') in {'running','completed','failed'}:
        raise AudienceError('New-chat preparation still shows a prior task. Open a fresh chat before this persona.')
    if kind=='resume_previous_task':
        previous_task=prior_task_session(run,session)
        if previous_task is None:raise AudienceError('No submitted task is recorded for this persona to resume.')
        previous_url=previous_task.get('conversation_url')
        if not previous_url or previous_url!=snapshot.get('url'):
            raise AudienceError('Resume must open this persona’s recorded task conversation URL, not another chat.')
    session['session_context']={'kind':kind,'url':str(context['url'])[:1500],'account_scope':'shared',
                                'model_history_scope':session['persona_id'],'prepared_at':time.time()}


def retry_session(run,session):
    """Explicit recovery of a failed decision; never replay a browser action."""
    if deadline_expired(run):raise AudienceError('Study deadline has expired; retry cannot extend it.')
    if session.get('status')!='error':raise AudienceError('Only an error session can be retried.')
    if session.get('pending_action') or session.get('unconfirmed_action'):
        raise AudienceError('An action is pending or unconfirmed; observe it before any retry. No action will be replayed.')
    history=session.setdefault('retry_history',[])
    if len(history)>=2:raise AudienceError('This session has used its two explicit retries.')
    if session.get('decisions',0)>=run['plan']['max_steps']:
        raise AudienceError('Decision limit is exhausted; retry cannot reset the step budget.')
    if run['plan'].get('session_mode')=='shared_account' and any(s['id']!=session['id'] and s['status']=='running' for s in run['sessions']):
        raise AudienceError('Shared browser is busy; finish the running session before retrying another.')
    history.append({'at_unix':time.time(),'decision_count':session.get('decisions',0),
                    'event_count':len(session.get('events',[])),
                    'previous_error':session.get('error',session.get('stop_reason','Unknown runtime error')),
                    'previous_feedback':session.get('feedback',{})})
    session.pop('error',None);session.pop('stop_reason',None)
    session['feedback']={};session['status']='running'


def bridge_lines(run):
    # Wait for host observations only inside the study deadline. StringIO is
    # intentionally supported for deterministic, network-free protocol tests.
    while not deadline_expired(run):
        try:descriptor=sys.stdin.fileno()
        except (AttributeError,OSError,ValueError):descriptor=None
        if descriptor is not None:
            remaining=max(0,run['runtime']['deadline_unix']-time.time())
            ready,_,_=select.select([descriptor],[],[],remaining)
            if not ready:return
        line=sys.stdin.readline()
        if not line:return
        yield line


def checkpoint(run,client,directory):
    run['ledger']=client.ledger
    write_json(directory/'run.json',run)
    diagnostics=getattr(client,'response_diagnostics',[])
    if diagnostics:
        path=directory/'action-responses.json'
        previous=load(path) if path.exists() else []
        if not isinstance(previous,list):raise AudienceError('Action-response audit must remain a JSON list; refusing to replace it.')
        merged=[];seen=set()
        for item in previous+diagnostics:
            key=(item.get('sequence'),item.get('model')) if isinstance(item,dict) and item.get('sequence') is not None and item.get('model') is not None else ('legacy',json.dumps(item,sort_keys=True,ensure_ascii=False))
            if key in seen:continue
            seen.add(key);merged.append(item)
        write_json(path,merged)


def finish_report(run, client, directory):
    # One budgeted synthesis per evidence fingerprint; offline `report` never
    # invokes a model or changes a recorded study.
    if deadline_expired(run):
        stop_at_deadline(run)
        run.setdefault('product_synthesis',{'status':'skipped','reason':'Общий лимит времени исчерпан; отчёт рассчитан по собранным событиям.'})
    else:enrich_run(run, client)
    checkpoint(run,client,directory)
    return build_report(run,directory)


def snapshot_barriers(snapshot):
    values=snapshot.get('policy_barriers',[]) if isinstance(snapshot,dict) else []
    return list(dict.fromkeys(redact(value[:600]) for value in values if isinstance(value,str) and value.strip())) if isinstance(values,list) else []


def record_browser_barrier(run, session, snapshot, barriers):
    """Retain the actual page and pending action without spending on a broken page."""
    started=session.setdefault('started_monotonic',time.monotonic())
    elapsed=time.monotonic()-started
    event_id=f"{session['id']}:e{len(session['events'])+1:03d}"
    reason='; '.join(barriers)
    session['events'].append({'id':event_id,
        'action':session.pop('pending_action',{'type':'observe'}),
        'observation':clean_snapshot(snapshot),
        'result':{'status':'blocked','reason':reason,'policy':'network','policy_barriers':barriers},
        'elapsed_ms':round(elapsed*1000)})
    session.update(status='blocked',stop_reason=reason,blocked_evidence_ids=[event_id],duration_s=round(elapsed,2))


def preflight_blocked(args, snapshot, barriers, client, directory):
    """A browser scout is evidence of a stopped test, not a synthetic persona."""
    plan={'url':args.url,'task':getattr(args,'task','Product preflight'),'audience':getattr(args,'audience',''),
          'budget_usd':args.budget,'personas':[],'models':[],'scenario_modes':[],
          'driver':'playwright','site_mode':args.site_mode,'planning_status':'not_started'}
    run=new_run(plan)
    run['preflight']={'status':'blocked','observation':clean_snapshot(snapshot),
                      'reason':'; '.join(barriers),'policy_barriers':barriers}
    run['warnings'].append('Предварительный просмотр остановлен ограничением браузера: '+ '; '.join(barriers)+'. Аудитория не запускалась; платное планирование не выполнялось.')
    if args.forecast_inputs:run['forecast_inputs']=load(args.forecast_inputs)
    write_json(directory/'plan.json',plan)
    return finish_report(run,client,directory)


def host(args):
    """JSON-lines process: separate persona histories, one host browser controller."""
    directory=Path(args.output).resolve();directory.mkdir(parents=True,exist_ok=True)
    existing=directory/'run.json'
    resume=getattr(args,'resume',False)
    if existing.exists() and not resume:raise AudienceError('Choose a new output directory or --resume; existing run will not be overwritten.')
    if resume and not existing.exists():raise AudienceError('No run.json checkpoint exists to resume.')
    run=load(existing) if resume else None
    ledger_path=ledger_for(args,directory)
    if resume:
        prior=run.get('runtime',{})
        prior_path=prior.get('ledger_path')
        if prior_path:
            if getattr(args,'ledger_path',None) and ledger_path!=Path(prior_path):raise AudienceError('Resume must use the original ledger.')
            ledger_path=Path(prior_path)
        if run['plan'].get('session_mode','isolated')!=getattr(args,'session_mode','isolated'):raise AudienceError('Resume must keep the original session mode.')
        if run['plan'].get('budget_usd')!=args.budget:raise AudienceError('Resume must keep the original budget cap.')
    with OpenRouterClient(key_for(args),budget_usd=args.budget,ledger_path=ledger_path) as client:
        runtime=runtime_start(args,client,run)
        if not resume:
            plan=plan_for(args,client,load(args.snapshot) if args.snapshot else None)
            run=new_run(plan);run['plan']['driver']='host-browser'
            if args.forecast_inputs:run['forecast_inputs']=load(args.forecast_inputs)
        attach_runtime(run,args,runtime,ledger_path)
        write_json(directory/'plan.json',run['plan']);checkpoint(run,client,directory)
        if stop_at_deadline(run):
            emit({'status':'time_limit','reports':finish_report(run,client,directory),'accounted_usd':float(client.spent_usd)});return
        catalogue=client.list_models()
        emit({'ready':True,'resumed':resume,'run_id':run['id'],'plan':run['plan'],
              'sessions':[session_hint(run,s) for s in run['sessions']],'next_session':session_hint(run),
              'deadline_unix':runtime['deadline_unix'],'accounted_usd':float(client.spent_usd),
              'protocol':'Send next + session_id + actual snapshot; first shared-account observation includes session_context:{kind:new_chat|fresh_journey|resume_previous_task,url:observed_url}. After each action include its actual result. Save literal messages with transcript + session_id + transcript before quit. status/report/quit/stop/retry supported; retry is explicit, error-only and limited to two attempts without resetting costs, steps or deadline. Actions are never replayed automatically.'})
        finished=False
        for line in bridge_lines(run):
            if not line.strip():continue
            try:
                if stop_at_deadline(run):break
                message=json.loads(line)
                if not isinstance(message,dict):raise AudienceError('Bridge command must be a JSON object.')
                command=message.get('command','next')
                if command=='next':
                    session=session_for(run,message['session_id'])
                    prepare_session(run,session,message)
                    if session.get('pending_action') and not isinstance(message.get('result'),dict):raise AudienceError('Observe the pending action and supply its actual result; never replay an action after resuming.')
                    session['conversation_url']=str(message['snapshot'].get('url',''))[:1500]
                    response=advance(run,session['id'],message['snapshot'],client,catalogue,message.get('result'))
                    stop_at_deadline(run);run['ledger']=client.ledger
                    checkpoint(run,client,directory);emit({**response,'next_session':session_hint(run)})
                elif command=='retry':
                    session=session_for(run,message['session_id'])
                    retry_session(run,session)
                    checkpoint(run,client,directory)
                    emit({'session_id':session['id'],'status':session['status'],'retry_count':len(session['retry_history']),
                          'next_session':session_hint(run),'instruction':'Send a fresh actual snapshot with next; no action has been issued or replayed.'})
                elif command=='transcript':
                    response=record_transcript(run,message['session_id'],message.get('transcript'))
                    checkpoint(run,client,directory);emit(response)
                elif command=='status':
                    emit({'next_session':session_hint(run),'sessions':[session_hint(run,s) for s in run['sessions']],
                          'remaining_seconds':max(0,round(runtime['deadline_unix']-time.time())),
                          'accounted_usd':float(client.spent_usd)})
                elif command=='stop':
                    session=session_for(run,message['session_id'])
                    status=message.get('status','blocked')
                    if status not in {'blocked','error','abandoned','step_limit','time_limit'}:raise AudienceError('Invalid stop status.')
                    session['status']=status;session['stop_reason']=str(message.get('reason','Host stopped session.'))[:600]
                    if session.get('pending_action'):session['unconfirmed_action']=session.pop('pending_action')
                    checkpoint(run,client,directory);emit({'session_id':session['id'],'status':status,'next_session':session_hint(run)})
                elif command in {'report','quit'}:
                    emit({'reports':finish_report(run,client,directory),'accounted_usd':float(client.spent_usd)})
                    if command=='quit':finished=True;break
                else:raise AudienceError('Unknown bridge command.')
            except (AudienceError,ValueError,KeyError,TypeError) as exc:
                emit({'error':str(exc)})
        if not finished:
            stop_at_deadline(run)
            emit({'reports':finish_report(run,client,directory),'accounted_usd':float(client.spent_usd),
                  'status':'time_limit' if deadline_expired(run) else 'input_closed'})


async def standalone(args):
    if getattr(args,'session_mode','isolated')!='isolated':raise AudienceError('Shared-account execution uses the host bridge; standalone requires isolated contexts.')
    from audience_core.browser import BrowserSession, origin_of
    directory=Path(args.output).resolve();directory.mkdir(parents=True,exist_ok=True)
    if (directory/'run.json').exists():raise AudienceError('Choose a new output directory; existing run will not be overwritten.')
    origins=[origin_of(args.url)]+(args.allow_origin or [])
    with OpenRouterClient(key_for(args),budget_usd=args.budget,ledger_path=ledger_for(args,directory)) as client:
        runtime=runtime_start(args,client)
        scout=BrowserSession(args.url,origins,mode=args.site_mode)
        try:
            await scout.start();snapshot=await scout.snapshot()
        finally:await scout.close()
        barriers=snapshot_barriers(snapshot)
        if barriers:
            emit({'event':'preflight_blocked','reports':preflight_blocked(args,snapshot,barriers,client,directory),'accounted_usd':float(client.spent_usd)})
            return
        plan=await asyncio.to_thread(plan_for,args,client,snapshot)
        run=new_run(plan);run['plan']['driver']='playwright';run['plan']['site_mode']=args.site_mode
        attach_runtime(run,args,runtime,ledger_for(args,directory))
        if args.forecast_inputs:run['forecast_inputs']=load(args.forecast_inputs)
        write_json(directory/'plan.json',plan);write_json(directory/'run.json',run)
        emit({'event':'planned','agents':len(plan['personas']),'models':plan['models'],'estimated_cost_usd':plan.get('estimated_cost_usd')})
        catalogue=client.list_models();semaphore=asyncio.Semaphore(args.concurrency)
        async def persona_worker(persona):
            async with semaphore:
                if stop_at_deadline(run):return
                browser=BrowserSession(args.url,origins,mode=args.site_mode,
                    evidence_dir=directory/'evidence'/persona['id'] if args.screenshots else None,
                    viewport={'width':390,'height':844} if persona.get('device')=='mobile' else {'width':1280,'height':900})
                own_sessions=[s for s in run['sessions'] if s['persona_id']==persona['id']]
                try:
                    await browser.start()
                    for session in own_sessions:
                        if stop_at_deadline(run):break
                        # Same browser context, storage and persona memory across these scenarios.
                        if session['mode']=='regular':
                            nav=await browser.act({'type':'navigate','url':args.url})
                            if nav.get('status')!='ok':
                                session['status']='blocked';session['stop_reason']=nav.get('reason','Could not revisit');continue
                        result=None
                        while session['status'] in {'pending','running'}:
                            if stop_at_deadline(run):break
                            # Re-observe immediately before each decision. This
                            # also collects asynchronous blocks since act()'s
                            # result snapshot, including initial-load requests.
                            observation=await browser.snapshot()
                            barriers=snapshot_barriers(observation)
                            if result:
                                barriers=list(dict.fromkeys(snapshot_barriers(result.get('snapshot'))+barriers))
                            if barriers:
                                record_browser_barrier(run,session,observation,barriers)
                                decision={'status':'blocked'}
                            else:
                                decision=await asyncio.to_thread(advance,run,session['id'],observation,client,catalogue,result)
                                if session['status'] in {'completed','abandoned','step_limit','error'}:
                                    # A background request may have been blocked
                                    # while the final model call was in flight.
                                    # Its charge remains in the shared ledger,
                                    # but its UX judgment must not be scored.
                                    try:
                                        final_observation=await browser.snapshot()
                                    except Exception as exc:
                                        session.update(status='error',feedback={},error=type(exc).__name__+': final browser observation failed')
                                        raise
                                    final_barriers=snapshot_barriers(final_observation)
                                    if final_barriers:
                                        record_browser_barrier(run,session,final_observation,final_barriers)
                                        session['feedback']={}
                            checkpoint(run,client,directory)
                            if session['status'] not in {'pending','running'}:break
                            result=await browser.act(decision['action'])
                        emit({'event':'session_finished','session_id':session['id'],'status':session['status']})
                except Exception as exc:
                    # Do not expose arbitrary browser/network exceptions; they can include URLs or secrets.
                    for session in own_sessions:
                        if stop_at_deadline(run):break
                        if session['status'] in {'pending','running'}:
                            session['status']='error';session['error']=type(exc).__name__+': browser/runtime failed'
                finally:
                    await browser.close();checkpoint(run,client,directory)
        try:
            await asyncio.wait_for(asyncio.gather(*(persona_worker(p) for p in plan['personas'])),
                                   timeout=max(.001,runtime['deadline_unix']-time.time()))
        except asyncio.TimeoutError:stop_at_deadline(run)
        emit({'reports':finish_report(run,client,directory),'accounted_usd':float(client.spent_usd)})


def main():
    parser=argparse.ArgumentParser(description='Audience — synthetic product users with OpenRouter.')
    sub=parser.add_subparsers(dest='command',required=True)
    models=sub.add_parser('models',help='List the live catalogue; no API key needed.')
    models.add_argument('--query',default='');models.add_argument('--output')
    models.add_argument('--eligible',action='store_true');models.add_argument('--limit',type=int,default=30)
    for name in ('plan','host','run'):
        p=sub.add_parser(name)
        p.add_argument('url');p.add_argument('--task',required=True);p.add_argument('--audience',default='')
        p.add_argument('--agents',default='auto');p.add_argument('--models',help='Exact comma-separated catalogue model IDs; omit for automatic selection.')
        p.add_argument('--budget',type=float,default=1.0);p.add_argument('--max-steps',type=int,default=12)
        p.add_argument('--ledger-path',help='Reuse the authoritative ledger across attempts; cap must match its original budget.')
        p.add_argument('--max-minutes',type=float,default=30,help='Overall wall-clock cap, including planning and final synthesis.')
        p.add_argument('--max-wait-seconds',type=int,default=180,help='Per-task bounded observation window while the product is working.')
        p.add_argument('--session-mode',choices=['isolated','shared_account'],default='isolated')
        if name=='host':p.add_argument('--resume',action='store_true',help='Resume this output checkpoint without replanning or resetting costs/deadline.')
        p.add_argument('--scenarios',help='first_use,resume,regular');p.add_argument('--prompt-key',action='store_true')
        p.add_argument('--device',choices=['auto','desktop','mobile'],default='auto')
        p.add_argument('--snapshot',help='Initial real browser snapshot JSON for product analysis.')
        p.add_argument('--output',default='audience-run');p.add_argument('--forecast-inputs')
        if name=='run':
            p.add_argument('--concurrency',type=int,default=3);p.add_argument('--site-mode',choices=['readonly','production','staging'],default='production')
            p.add_argument('--allow-origin',action='append');p.add_argument('--screenshots',action='store_true')
    report=sub.add_parser('report');report.add_argument('run');report.add_argument('--output')
    report.add_argument('--forecast-inputs',help='Explicit external assumptions; rebuild reports without model calls.')
    args=parser.parse_args()
    try:
        if args.command=='models':
            from audience_core.openrouter import model_eligibility
            client=OpenRouterClient(budget_usd=0);catalogue=client.list_models();client.close()
            selected=[m for m in catalogue if args.query.lower() in (m['id']+' '+m.get('name','')).lower()]
            if args.eligible:selected=[m for m in selected if model_eligibility(m)[0]]
            if args.output:write_json(args.output,selected)
            emit({'total_catalogue':len(catalogue),'matched':len(selected),'models':[
                {'id':m['id'],'name':m.get('name'),'context_length':m.get('context_length'),'pricing':m.get('pricing'),
                 'eligible':model_eligibility(m)[0],'eligibility_reason':model_eligibility(m)[1]} for m in selected[:args.limit]],'saved':args.output})
        elif args.command=='report':
            run=load(args.run)
            if args.forecast_inputs:run['forecast_inputs']=load(args.forecast_inputs)
            ledger_path=Path(run.get('runtime',{}).get('ledger_path') or Path(args.run).parent/'usage.json')
            if ledger_path.exists():
                usage=load(ledger_path)
                if not isinstance(usage,dict) or not isinstance(usage.get('ledger'),list):raise AudienceError('Authoritative usage ledger is invalid.')
                run['ledger']=usage['ledger']
                for entry in run['ledger']:
                    if entry.get('cost_status')=='reserved':
                        entry['cost_status']='unknown';entry['status']='error';entry['error']='interrupted_or_still_in_flight'
                run.setdefault('warnings',[]).append('Cost accounting reconciled from the durable usage ledger.')
            emit({'reports':build_report(run,Path(args.output or Path(args.run).parent))})
        else:
            if not 0<args.budget<=10000:raise AudienceError('Budget must be >0 and <=10000 USD.')
            if not math.isfinite(args.max_minutes) or not 0<args.max_minutes<=1440:raise AudienceError('max-minutes must be >0 and <=1440.')
            if not 1<=args.max_wait_seconds<=600:raise AudienceError('max-wait-seconds must be 1..600.')
            if not 1<=args.max_steps<=100:raise AudienceError('max-steps must be 1..100.')
            if args.agents!='auto' and (not args.agents.isdigit() or not 1<=int(args.agents)<=1000):raise AudienceError('agents must be auto or 1..1000.')
            if args.command=='plan':
                directory=Path(args.output);directory.mkdir(parents=True,exist_ok=True)
                with OpenRouterClient(key_for(args),budget_usd=args.budget,ledger_path=ledger_for(args,directory)) as client:
                    runtime_start(args,client)
                    plan=plan_for(args,client,load(args.snapshot) if args.snapshot else None)
                    write_json(directory/'plan.json',plan);emit(plan)
            elif args.command=='host':host(args)
            else:
                if not 1<=args.concurrency<=8:raise AudienceError('Concurrency must be 1..8.')
                asyncio.run(standalone(args))
    except (AudienceError,ValueError,OSError) as exc:
        emit({'error':str(exc)});return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
