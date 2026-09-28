#!/usr/bin/env python3
"""Opt-in native Codex fixture harness. No real model, account, or production writes.

Run manually: python3 tests/native_harness.py --output /tmp/acgm-native-results.json
Uses a temporary CODEX_HOME, vetted hook commands and loopback Responses fixtures.
Hook trust bypass is scoped to this temporary invocation, never persisted.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import test_runtime as R

CODEX = shutil.which('codex')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    fixture=R.RuntimeTests();fixture.setUp();fixture.project=fixture.project.resolve();fixture.init_activate()
    base=fixture.base;home=base/'home';home.mkdir()
    data=fixture.data
    cache=Path.home()/'.codex/models_cache.json'
    if cache.exists():shutil.copy2(cache,home/'models_cache.json')
    (data/'runtime').mkdir(parents=True);shutil.copy2(R.RUNTIME,data/'runtime/acgm_codex.py')
    calls=[];usage=1000;sequence=[];counter=0
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def do_POST(self):
            nonlocal counter
            request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            request_text=json.dumps(request,ensure_ascii=False)
            calls.append({'path':self.path,'input_items':len(request.get('input',[])),
                          'profiles':[p for p in ('light','standard','strict')
                                      if 'Initial workflow profile: '+p in request_text]})
            counter+=1
            command=sequence.pop(0) if sequence else None
            if callable(command):command=command()
            if command is not None:
                arguments=command if isinstance(command,dict) else {'cmd':command,'max_output_tokens':200,'yield_time_ms':10000,'login':False}
                item={'type':'function_call','id':f'fc_{counter}','call_id':f'call_{counter}','name':'exec_command','arguments':json.dumps(arguments)}
            else:
                item={'type':'message','id':f'msg_{counter}','role':'assistant','content':[{'type':'output_text','text':'Synthetic fixture complete.'}]}
            events=[{'type':'response.created','response':{'id':f'r{counter}','status':'in_progress','output':[]}},
                    {'type':'response.output_item.added','output_index':0,'item':item},
                    {'type':'response.output_item.done','output_index':0,'item':item},
                    {'type':'response.completed','response':{'id':f'r{counter}','status':'completed','output':[item],
                    'usage':{'input_tokens':usage,'output_tokens':20,'total_tokens':usage+20,'input_tokens_details':{'cached_tokens':0}}}}]
            body=''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events).encode()
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    server=HTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    (home/'config.toml').write_text(f'''model = "gpt-6-astra"
model_provider = "fixture"
model_context_window = 500000
model_auto_compact_token_limit = 450000
model_auto_compact_token_limit_scope = "total"
approval_policy = "never"
[model_providers.fixture]
name = "Fixture"
base_url = "http://127.0.0.1:{server.server_port}/v1"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
[features]
plugins = false
''')
    capture=home/'capture.py'
    capture.write_text("import json,sys,pathlib\np=json.load(sys.stdin)\nwith pathlib.Path("+repr(str(base/'hook-input.jsonl'))+").open('a') as f:f.write(json.dumps(p)+'\\n')\nprint('{}')\n")
    hooks=json.loads((R.REPO/'hooks/hooks.json').read_text())
    prefix='env '+ ' '.join(shlex.quote(k+'='+str(v)) for k,v in {'PLUGIN_ROOT':R.REPO,'PLUGIN_DATA':data,'ACGM_CODEX_DATA_DIR':data}.items())+' '
    for event,groups in hooks['hooks'].items():
        for group in groups:
            for hook in group['hooks']:hook['command']=prefix+hook['command']
        groups.append({'hooks':[{'type':'command','command':'python3 '+shlex.quote(str(capture))}]})
    (home/'hooks.json').write_text(json.dumps(hooks))
    env={**fixture.env,'CODEX_HOME':str(home),'PATH':str(R.REPO/'bin')+os.pathsep+os.environ['PATH']}
    for key in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy']:env.pop(key,None)
    env['NO_PROXY']=env['no_proxy']='127.0.0.1,localhost'
    rows=[]
    def run(name,commands,*,sandbox='workspace-write',prompt='Synthetic fixture only.',resume=None):
        nonlocal sequence
        sequence=list(commands);before=len(calls)
        argv=[CODEX,'exec','--json','--dangerously-bypass-hook-trust','--skip-git-repo-check','-C',str(fixture.project),'--sandbox',sandbox]
        if resume:argv+=['resume',resume]
        argv.append(prompt)
        p=subprocess.run(argv,env=env,input='',capture_output=True,text=True,timeout=40)
        parsed=[]
        for line in p.stdout.splitlines():
            try:parsed.append(json.loads(line))
            except ValueError:pass
        thread=next((e.get('thread_id') for e in parsed if e.get('type')=='thread.started'),resume)
        row={'case':name,'returncode':p.returncode,'native':parsed,'stderr':p.stderr[-2000:],'fixture_response_requests':len(calls)-before}
        row['profiles_seen']=sorted({profile for call in calls[before:] for profile in call['profiles']})
        if thread:
            audit=subprocess.run([sys.executable,str(R.REPO/'scripts/session_guardian.py'),'audit','--project',str(fixture.project),'--thread',thread],env=env,capture_output=True,text=True)
            try:row['audit']=json.loads(audit.stdout)
            except ValueError:row['audit']={'error':audit.stderr[-500:]}
        rows.append(row)
        print(name,p.returncode,len(calls)-before,flush=True)
        return thread
    def approval_control(decision):
        # Native approval control fixture has no plugin trust state. Its ACGM
        # coverage is explicitly absent, rather than manufactured by replay.
        import queue
        approval_home=base/('approval-'+decision);approval_home.mkdir()
        shutil.copy2(home/'config.toml',approval_home/'config.toml')
        if (home/'models_cache.json').exists():shutil.copy2(home/'models_cache.json',approval_home/'models_cache.json')
        environment={**env,'CODEX_HOME':str(approval_home)}
        command='printf approved > approval-'+decision+'.txt'
        nonlocal sequence
        sequence=[{'cmd':command,'sandbox_permissions':'require_escalated','justification':'Authorized temporary fixture'}]
        process=subprocess.Popen([CODEX,'app-server','--stdio'],env=environment,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        inbox=queue.Queue()
        def receive():
            for line in process.stdout:
                try:inbox.put(json.loads(line))
                except ValueError:pass
        threading.Thread(target=receive,daemon=True).start()
        def send(message):process.stdin.write(json.dumps(message)+'\n');process.stdin.flush()
        def response(number):
            while True:
                message=inbox.get(timeout=30)
                if message.get('id')==number:return message
        records=[]
        try:
            send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'acgm-fixture','version':'1'},'capabilities':{'experimentalApi':True}}});response(1)
            send({'method':'initialized','params':{}})
            send({'id':2,'method':'thread/start','params':{'cwd':str(fixture.project),'model':'gpt-6-astra','modelProvider':'fixture','approvalPolicy':'on-request','approvalsReviewer':'user','sandbox':'read-only','ephemeral':True}})
            started=response(2)
            if 'error' in started:raise RuntimeError(str(started))
            thread=started['result']['thread']['id']
            send({'id':3,'method':'turn/start','params':{'threadId':thread,'input':[{'type':'text','text':'Temporary approval fixture only.','text_elements':[]}]}})
            while True:
                message=inbox.get(timeout=30)
                method=message.get('method','')
                if method=='item/commandExecution/requestApproval':
                    params=message['params']
                    if command not in str(params):raise RuntimeError('Unexpected approval target')
                    records.append({'event':'approval-requested','decision':decision})
                    send({'id':message['id'],'result':{'decision':decision}})
                elif method=='item/completed':
                    item=message['params']['item']
                    if item.get('type')=='commandExecution':records.append({'event':'execution','status':item.get('status'),'exit_code':item.get('exitCode')})
                elif method=='turn/completed':break
            exists=(fixture.project/('approval-'+decision+'.txt')).exists()
            rows.append({'case':'native-approval-'+decision,'native':records,'file_exists':exists,
                         'acgm':'No plugin in this isolated approval control; no ACGM execution claim.'})
            print('native-approval-'+decision,records,exists,flush=True)
        finally:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()

    try:
        approval_control('decline')
        approval_control('accept')
        run('local-safe-read',['pwd'])
        run('local-mutation',["printf fixture > mutation.txt"])
        run('execution-failure',['exit 7'])
        run('sandbox-block',["printf forbidden > blocked.txt"],sandbox='read-only')
        rows[-1]['blocked_file_exists']=(fixture.project/'blocked.txt').exists()
        run('approval-deny',[{'cmd':'printf forbidden > denied.txt','sandbox_permissions':'require_escalated','justification':'fixture only'}])
        rows[-1]['denied_file_exists']=(fixture.project/'denied.txt').exists()
        run('compound-deny',['true && rm -rf nonexistent-fixture'])
        # Reuse the same real Hooks with a baseline-protected Light decision.
        workflow=fixture.project/'.governance/decisions/acgm-policy.json'
        workflow.write_text(json.dumps({'schema':'acgm-workflow-policy-v1',
                                        'capability':'high-autonomy','profile':'auto'}))
        fixture.cli('activate',str(fixture.project),check=True)
        run('profile-light-read',['pwd'])
        run('profile-light-destructive-deny',['rm -rf light-fixture'])
        outside=base/'not-a-repository';outside.mkdir()
        def failed_arm():
            source=fixture.latest_event('gate-denied')
            return ('acgm-codex gate arm --event '+source['event_id']+
                    ' --category '+source['category']+' --target '+shlex.quote(str(outside)))
        escalated=run('profile-repeated-fixed-check-failure',
                      ['git -C '+shlex.quote(str(outside))+' reset --hard',failed_arm,failed_arm])
        run('profile-escalation-resume',['true'],resume=escalated)
        ordinary=run('profile-new-session-light',['true'])
        record=fixture.project/'.governance/decisions/continuity.md'
        record.write_text('# Accepted project constraint\nKEEP_API; migration verification unfinished.\n')
        run('records-resume', ['cat .governance/decisions/continuity.md'], resume=ordinary)
        rows[-1]['record_intact']=record.read_text().endswith('migration verification unfinished.\n')
        policy=fixture.project/'.acgm/session-guardian.json'
        from test_session_hooks import POLICY
        policy.write_text(json.dumps(POLICY))
        for name,used in [('low-context',1000),('warning-35',310000),('handoff-20',381000),('critical',391000)]:
            usage=used
            thread=run(name,['true','true'])
        run('continue-once',['true'],prompt='ACGM 继续一次\nfinish the fixture',resume=thread)
        run('next-prompt-blocked',['true'],prompt='new business request',resume=thread)
        run('handoff',['true'],prompt='ACGM 交接',resume=thread)
        usage=451000
        run('auto-compaction-intercept',['true','true'])
        usage=1000
        run('new-session-clean',['true'])
        import urllib.request
        panel=subprocess.Popen([sys.executable,str(R.REPO/'scripts/session_dashboard.py'),'--project',str(fixture.project),'--codex-home',str(home)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
        try:
            url=panel.stdout.readline().strip()
            before=len(calls)
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            samples=[json.load(opener.open(url+'status',timeout=5)) for _ in range(3)]
            rows.append({'case':'dashboard-no-model-calls','polls':3,'fixture_response_requests':len(calls)-before,'task_counts':[len(x.get('tasks',[])) for x in samples]})
        finally:panel.terminate();panel.wait(timeout=5)
        hook_inputs=[json.loads(line) for line in (base/'hook-input.jsonl').read_text().splitlines()]
        # Raw inputs remain ephemeral. Summaries do not copy model/user content.
        payload={'codex_version':subprocess.check_output([CODEX,'--version'],env=env,text=True).strip(),
                 'mode':'native CLI + fixed local Responses; temporary home and vetted hooks',
                 'rows':rows,'hook_events':{e:sum(p['hook_event_name']==e for p in hook_inputs) for e in sorted({p['hook_event_name'] for p in hook_inputs})},
                 'posttool_response_types':sorted({type(p.get('tool_response')).__name__ for p in hook_inputs if p['hook_event_name']=='PostToolUse'}),
                 'ledger':fixture.report_json()['events']}
        # Exit status alone is not acceptance: denied operations often finish
        # their model turn successfully. Check execution, artifacts and ledger.
        by_name={row['case']:row for row in rows}
        def completed(name):
            return [e['item'] for e in by_name[name].get('native',[])
                    if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='command_execution']
        checks={
            'native-approval-decline':not by_name['native-approval-decline']['file_exists'],
            'native-approval-accept':by_name['native-approval-accept']['file_exists'],
            'safe-read':any(e.get('exit_code')==0 for e in completed('local-safe-read')),
            'mutation':(fixture.project/'mutation.txt').read_text()=='fixture',
            'failed-execution':any(e.get('exit_code')==7 for e in completed('execution-failure')),
            'sandbox-block':not by_name['sandbox-block']['blocked_file_exists'],
            'approval-policy-deny':not by_name['approval-deny']['denied_file_exists'],
            'compound-deny':not completed('compound-deny'),
            'light-quiet':not by_name['profile-light-read']['profiles_seen'] and bool(completed('profile-light-read')),
            'light-destructive-deny':not completed('profile-light-destructive-deny'),
            'fixed-check-failures':sum(e.get('exit_code')==3 for e in completed('profile-repeated-fixed-check-failure'))==2,
            'strict-after-resume':'strict' in by_name['profile-escalation-resume']['profiles_seen'],
            'new-session-quiet':not by_name['profile-new-session-light']['profiles_seen'] and bool(completed('profile-new-session-light')),
            'records-readable-on-resume':any(e.get('exit_code')==0 and 'KEEP_API' in e.get('aggregated_output','') for e in completed('records-resume')) and by_name['records-resume']['record_intact'],
            'escalation-recorded':sum(e['kind']=='policy-escalated' for e in payload['ledger'])==1,
            'quiet-with-guardian':not by_name['low-context']['profiles_seen'] and bool(completed('low-context')),
            'continue-once':bool(completed('continue-once')),
            'next-prompt-blocked':by_name['next-prompt-blocked']['fixture_response_requests']==0,
            'handoff':bool(completed('handoff')),
            'precompact':by_name['auto-compaction-intercept']['returncode']==1 and by_name['auto-compaction-intercept']['fixture_response_requests']==1,
            'new-session-clean':bool(completed('new-session-clean')),
            'dashboard-no-model':by_name['dashboard-no-model-calls']['fixture_response_requests']==0 and all(by_name['dashboard-no-model-calls']['task_counts']),
        }
        payload['checks']=checks
        payload['ok']=all(checks.values())
        args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
        if not payload['ok']:raise AssertionError('Native acceptance failed: '+', '.join(k for k,v in checks.items() if not v))
    finally:
        server.shutdown();fixture.tearDown()


if __name__=='__main__':main()
