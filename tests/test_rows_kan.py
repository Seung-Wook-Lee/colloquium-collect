"""11/26 의장 "데이터베이스칸으로 합쳐": 공부자료·주가뉴스 후보·판정은 10년치 데이터베이스 줄 칸 하나(px_store.rows/put_day)."""
import io
import pathlib
import sys

import pandas as pd

R = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(R / 'collect' / 'data')]
import px_store as PS  # noqa: E402


class FakeDrive:
    def __init__(self, files):
        self.f, self.trashed = dict(files), []

    def get(self, p):
        return self.f.get(p)

    def put(self, p, b):
        self.f[p] = b

    def trash(self, p):
        self.trashed.append(p); self.f.pop(p, None)

    def ls(self, folder):
        return [{'name': k.rsplit('/', 1)[1]} for k in self.f if k.rsplit('/', 1)[0] == folder]


def _csv(df):
    return df.to_csv(index=False).encode('utf-8-sig')


def test_study_migrate_and_put_day():
    B = PS.BASE
    d = FakeDrive({f'{B}/위원공부/후보/20261125_공부후보.csv': _csv(pd.DataFrame({'번호': [1, 2], '링크': ['a', 'b']})),
                   f'{B}/위원공부/후보/20261124_공부후보.csv': _csv(pd.DataFrame({'번호': [1], '링크': ['c']}))})
    T = PS.rows(d, '공부후보', log=lambda *_: None)
    assert sorted(T['후보날짜'].unique()) == ['20261124', '20261125'] and len(T) == 3
    assert len(d.trashed) == 2 and f'{B}/1_data/{PS.name("공부후보")}' in d.f
    PS.put_day(d, '공부후보', '후보날짜', '20261126', pd.DataFrame({'번호': [1], '링크': ['z']}))
    T = PS.rows(d, '공부후보')
    assert len(T) == 4 and (T['후보날짜'] == '20261126').sum() == 1
    PS.put_day(d, '공부후보', '후보날짜', '20261126', pd.DataFrame({'번호': [1, 2], '링크': ['z', 'y']}))
    assert (PS.rows(d, '공부후보')['후보날짜'] == '20261126').sum() == 2


def test_no_old_paths_in_pages():
    for f in ('app/pages/4_주가뉴스_고르기.py', 'app/pages/5_공부자료_승인.py'):
        s = (R / f).read_text(encoding='utf-8')
        assert 'drive.put(' not in s and '_공부후보.csv' not in s and '주가뉴스후보.csv' not in s, f


def test_ready_counts_today():
    T = pd.DataFrame({'후보날짜': ['20261126', '20261126', '20261125'], '링크': ['a', 'b', 'c']})
    N = pd.DataFrame({'날짜': ['2026-11-26', '2026-11-25'], '제목': ['x', 'y']})
    import gzip
    f = {f'{PS.BASE}/1_data/{PS.name("공부후보")}': gzip.compress(T.to_csv(index=False).encode('utf-8-sig')),
         f'{PS.BASE}/1_data/{PS.name("주가뉴스후보")}': gzip.compress(N.to_csv(index=False).encode('utf-8-sig'))}
    assert PS.ready(FakeDrive(f), '20261126', lambda *_: None) == {'공부후보': 2, '주가뉴스후보': 1}


def test_study_gather_reads_log_not_fetch():
    s = (R / 'app' / 'meeting' / 'study.py').read_text(encoding='utf-8')
    assert 'fetch_rss' not in s.split('def gather')[1].split('\ndef ')[0].replace('events.fetch_rss를', '')
