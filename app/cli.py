import argparse, json
from .pipeline import build
p=argparse.ArgumentParser(description='ViralFlow V12')
p.add_argument('--topic',default='L’homme qui a survécu à deux bombes nucléaires')
a=p.parse_args(); print(json.dumps(build(a.topic),ensure_ascii=False,indent=2))
