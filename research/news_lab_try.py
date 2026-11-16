# 뉴스 실험실 첫 시험 실행(새 워크플로는 머지 전에는 손으로 못 돌려 조사 실행으로 대신 부른다, 2026-11-14)
import runpy, sys
sys.argv = ['news_lab/run.py']
runpy.run_path('news_lab/run.py', run_name='__main__')
