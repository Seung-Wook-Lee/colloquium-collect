# 드라이브 창구 — GitHub에서 돌 때 의장님 구글 드라이브와 파일을 주고받는다.
#   드라이브 쪽 창구는 apps_script/Code.gs (의장님 계정으로 도는 Apps Script 웹앱)
#   비밀값: DRIVE_URL(웹앱 주소), DRIVE_TOKEN(Code.gs의 setup()이 만든 토큰)
#   경로는 '내 드라이브' 기준: '콜로키움 수집데이터/20261028/20261028_시세.csv'
import base64, os, time
import requests

URL = os.environ.get('DRIVE_URL', '').strip()
TOKEN = os.environ.get('DRIVE_TOKEN', '').strip()


def _call(payload, retry=3):
    for n in range(retry + 1):
        try:
            r = requests.post(URL, json={'token': TOKEN, **payload}, timeout=300)
            r.raise_for_status()
            j = r.json()
            if not j.get('ok'):
                raise RuntimeError(j.get('error'))
            return j
        except Exception as e:
            if n == retry or '토큰' in str(e) or '허용되지' in str(e):
                raise RuntimeError(f'드라이브 {payload.get("action")} {payload.get("path")}: {e}') from None
            time.sleep(5 * (n + 1))


def ready():
    return bool(URL and TOKEN)


def ls(folder):
    """폴더 안 파일 목록 [{name, size, modified}] (폴더가 없으면 빈 목록)"""
    return _call({'action': 'list', 'path': folder})['files']


def get(path):
    """파일 내용(bytes). 없으면 None"""
    j = _call({'action': 'get', 'path': path})
    return base64.b64decode(j['data']) if j.get('found') else None


MIME = {'.csv': 'text/csv', '.txt': 'text/plain', '.pdf': 'application/pdf', '.html': 'text/html',
        '.json': 'application/json', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}


def put(path, data):
    """파일 올리기 (같은 이름이 있으면 바꿔 넣음)"""
    mime = MIME.get(os.path.splitext(path)[1].lower(), 'application/octet-stream')
    return _call({'action': 'put', 'path': path, 'mime': mime, 'data': base64.b64encode(data).decode()})
