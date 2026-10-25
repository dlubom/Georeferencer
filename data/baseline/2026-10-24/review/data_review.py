"""Read-only audit of committed parquet/YAML. Produces only stdout JSON."""
from pathlib import Path
import ast, importlib.util, json
import numpy as np, pandas as pd, yaml
ROOT=Path(__file__).resolve().parents[4]
s=pd.read_parquet(ROOT/'parquet/SUBMISSIONS.parquet');c=pd.read_parquet(ROOT/'parquet/CAVES.parquet');a=pd.read_parquet(ROOT/'parquet/ASSIGNMENTS.parquet')
spec=importlib.util.spec_from_file_location('extract',ROOT/'pipeline/01_extract_yaml.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
metas={p.parent.name:yaml.safe_load(p.read_text()) for p in (ROOT/'data/caves').glob('*/meta.yaml')}
byinv={v['cave']['inventory_number']:(k,v) for k,v in metas.items()}
test_effects=[];invalid_north=[];spreads=[]
for cid,g in s.groupby('cave_id'):
 t=g['Unnamed: 52'].eq('TEST')
 if t.any():
  aa=m.aggregate_cave(cid,g,c)['yaml_data'];bb=m.aggregate_cave(cid,g[~t],c)['yaml_data'];d,cur=byinv[cid]
  test_effects.append(dict(cave_id=cid,dir_id=d,n_all=len(g),n_test=int(t.sum()),n_real=len(g[~t]),users_all=g.user_id.nunique(),users_real=g[~t].user_id.nunique(),values={k:{'with_test':aa[k],'without_test':bb[k],'current':cur[k]} for k in ['entrance','scale','north','quality']}))
 north=g[g.skipNorth==False];counts=north.points_orig_json.map(lambda x:len(json.loads(x)))
 if (counts<5).any():
  good=north[counts>=5];d,cur=byinv[cid]
  invalid_north.append(dict(cave_id=cid,dir_id=d,invalid_rows=int((counts<5).sum()),valid_rows=len(good),north_values=north.north_deg.tolist(),current=cur['north'],flag=cur['quality']['flag']))
 if len(north)>1 and north.north_deg.max()-north.north_deg.min()>1:
  d,cur=byinv[cid];spreads.append(dict(cave_id=cid,dir_id=d,north_values=north.north_deg.tolist(),current=cur['north'],flag=cur['quality']['flag']))
# AST-assisted proof of --image-id ignored; no execution or external files needed.
source=(ROOT/'pipeline/05_add_cave.py').read_text();tree=ast.parse(source)
manual={'image_id_argument_declared_at':[n.lineno for n in ast.walk(tree) if isinstance(n,ast.Call) and any(isinstance(x,ast.Constant) and x.value=='--image-id' for x in n.args)],'args_image_id_reads':[n.lineno for n in ast.walk(tree) if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Name) and n.value.id=='args' and n.attr=='image_id'],'first_plan_selection_at':63,'arbitrary_tif_fallback_at':74}
report=pd.read_csv(ROOT/'data/caves/_reports/summary.csv',dtype={'dir_id':str});missing=pd.read_csv(ROOT/'data/caves/_reports/missing.csv')
report_stats={'summary_rows':len(report),'yaml_count':len(metas),'missing_report_rows':len(missing),'actual_missing_tif_or_tfw':sum(not (ROOT/'data/caves'/d/'image.tif').exists() or not (ROOT/'data/caves'/d/'image.tfw').exists() for d in metas),'north_angle_changes':[{'dir_id':r.dir_id,'reported':r.north_angle_deg,'current':metas[r.dir_id]['north']['angle_deg']} for r in report.itertuples() if r.north_angle_deg!=metas[r.dir_id]['north']['angle_deg']]}
elig=[g for _,g in s.groupby('cave_id') if len(g)>=5]
out={'head':'fad70f09992671a0da5a364dfea4a2c538f80e3d','counts':{'submissions':len(s),'test_rows':int(s['Unnamed: 52'].eq('TEST').sum()),'orphan_assignments':int((~s.assignment_id.isin(a.assignment_id)).sum()),'eligible_caves':len(elig),'eligible_below_5_users':sum(g.user_id.nunique()<5 for g in elig),'eligible_below_5_non_test_users':sum(g[~g['Unnamed: 52'].eq('TEST')].user_id.nunique()<5 for g in elig),'current_yaml':len(metas),'manual_yaml':sum(x['cave']['n_submissions']==0 for x in metas.values())},'test_effects':test_effects,'invalid_north':invalid_north,'north_spreads_over_1_deg':spreads,'manual_image_selection':manual,'reports':report_stats}
print(json.dumps(out,ensure_ascii=False,indent=2))
