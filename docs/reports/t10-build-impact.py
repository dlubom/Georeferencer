"""Odtwarzalny audyt T10; wejście T09 musi mieć oryginalny hash."""
import argparse
import ast, hashlib, importlib.util, json, subprocess, sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--before',type=Path,required=True)
parser.add_argument('--protected-changes',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'pipeline'))
import orientation
from coordinate_source import verify, read_rows, sha256
from gps_kataster_coordinates import load_best_measurements
base='16f5cb2f3ea101b2552f9536673146c4ed8a6b74'
before_bytes=args.before.read_bytes()
if hashlib.sha256(before_bytes).hexdigest() != 'b5aa6dead25fbb546a50ca4718bc481622131d6380a6b358dd244e6027b78183':
    raise SystemExit('Wymagany oryginalny generator T09 z commitu bazowego')
before_source=before_bytes.decode()
protected_changes=args.protected_changes.read_text().splitlines()
def load(source,name):
    import types
    module=types.ModuleType(name)
    module.__file__=str(root/'pipeline/02_generate_geotiff.py')
    exec(compile(source,module.__file__,'exec'),module.__dict__)
    return module
before=load(before_source,'before')
after_source=(root/'pipeline/02_generate_geotiff.py').read_text()
after=load(after_source,'after')
def nodes(source):
    result={}
    for node in ast.parse(source).body:
        if isinstance(node,ast.FunctionDef) and node.name in ('compute_world_file','update_computed_section','write_tfw'):
            result[node.name]=ast.dump(node,include_attributes=False)
        if isinstance(node,ast.Assign) and any(isinstance(n,ast.Name) and n.id=='GEOMETRY' for n in node.targets):
            result['GEOMETRY']=ast.dump(node,include_attributes=False)
    return result
index=load_best_measurements(verify())
rows=read_rows(verify())
records=[]
changed=[]
for directory in after.find_caves(root/'data/caves'):
    old_meta,old=before.prepare_cave(directory,index)
    new_meta,new=after.prepare_cave(directory,index)
    if old!=new: changed.append(directory.name)
    records.append({'plan':directory.name,'inputs':after.input_hashes(directory),'parameters':new,
                    'measurement':rows[new_meta['coordinates']['gps_kataster_object_id']]})
report={'task':'T10 / #15','base_commit':base,'plans':len(records),
        'source_files_changed':protected_changes, 'georeferencing_changed_plans':changed,
        'geometry_functions_ast_identical':nodes(before_source)==nodes(after_source),
        'parameters_identical_to_t09':not changed,
        'new_plans':[], 'removed_plans':[], 'exceptions_updated':False,'history_hashes_updated':False,
        'catalogue_inputs_and_parameters_sha256':hashlib.sha256(json.dumps(records,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
        'protected_paths':['data/caves','data/qa','data/baseline','data/history','data/coordinate-source','data/validation','data/classification','data/migrations','parquet','docs/reports/t05*','docs/reports/t06*','docs/reports/t07*','docs/reports/t08*','docs/reports/t09*'],
        'contract_changes':['Domyślne osobne wyniki i computed.json zamiast zapisu do źródeł','Pełne --changed według treści, bez mtime','ZIP: manifest i trzy artefakty na plan, zamiast płaskiego globu TIFF','Testy zakresu Git/wrappera na hoście, GDAL/historia/QA w przypiętym kontenerze']}
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
print(json.dumps({'plans':len(records),'changed_geometry':len(changed),'ast_identical':report['geometry_functions_ast_identical']}))

if changed or protected_changes or not report['geometry_functions_ast_identical']:
    raise SystemExit(1)
