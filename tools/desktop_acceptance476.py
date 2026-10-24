"""Start the installed runtime, verify real launcher admission, stop it cleanly."""
from pathlib import Path
import argparse,json,os,subprocess,tempfile,time,urllib.request
from http.cookiejar import CookieJar


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-python',required=True)
    args=parser.parse_args();source=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='eagleeye-desktop-') as directory:
        root=Path(directory);workspace=root/'workspace'
        env={**os.environ,'EAGLEEYE_DATA_DIR':str(workspace),'EAGLEEYE_SETTINGS_DIR':str(root/'settings')}
        log=(root/'console.log').open('w',encoding='utf-8')
        process=subprocess.Popen([str(Path(args.runtime_python).resolve()),'-I','-m','eagleeye.bootstrap.desktop476',
            '--install-root',str(source),'--no-browser'],env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+60
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(CookieJar()))
            while time.monotonic()<deadline:
                if process.poll() is not None:raise RuntimeError('Installed desktop process stopped before readiness')
                try:
                    runtime=json.loads((workspace/'data/runtime_126_0/workspace.json').read_text())
                    base='http://127.0.0.1:'+str(int(runtime['port']))
                    with opener.open(base+'/health',timeout=.5) as response:health=json.load(response)
                    if health.get('ok'):break
                except (OSError,ValueError):time.sleep(.2)
            else:raise RuntimeError('Installed desktop health timeout')
            token=(workspace/'data/security_364/local_session_token').read_text().strip()
            from urllib.parse import urlencode
            with opener.open(base+'/security/start?'+urlencode({'token':token}),timeout=3) as response:
                assert response.status==200 and 'Systemadministrator anlegen' in response.read().decode()
            print(json.dumps({'desktop_start':'pass','build':health['build'],'launcher_admission':'pass',
                              'browser_window_tested':False,'credentials_in_report':False}))
        finally:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            log.close()
if __name__=='__main__':main()
