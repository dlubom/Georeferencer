import sys, importlib.util, tempfile, json, csv, math
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'pipeline'))
import gps_kataster_coordinates as gps
import yaml
from PIL import Image
spec=importlib.util.spec_from_file_location('gen',ROOT/'pipeline/02_generate_geotiff.py')
gen=importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)
base=gps.BestMeasurementRow(object_id='OBJ-1',category='jaskinia_otwor',name_local='Test',cave_id='C-1',measurement_id='M-1',lat=49.2,lon=19.8,x_1992='',y_1992='',source='',source_ref='',nr_inwent='',pig_id='',tpn_globalid='',verification_status='')
index=gps.GpsKatasterIndex([base])
meta={'cave':{'dir_id':'test','name':'Test'},'coordinates':{'gps_kataster_object_id':'OBJ-1','lat':49.0,'lon':19.0},'image':{'width':4,'height':4},'entrance':{'x':2.0,'y':2.0},'scale':{'pixels_per_meter':1.0},'north':{'angle_deg':0.0},'declination_deg':0.0}
with tempfile.TemporaryDirectory() as td:
    p=Path(td); Image.new('1',(4,4),1).save(p/'image.tif'); (p/'meta.yaml').write_text(yaml.safe_dump(meta))
    ok,msg=gen.process_cave(p,index,True)
    data=yaml.safe_load((p/'meta.yaml').read_text())
    xy=gen.TRANSFORMER.transform(19.0,49.0); expected=gen.TRANSFORMER.transform(base.lon,base.lat)
    print(json.dumps({'strict_numeric_coords_success':ok,'retained_coords':data['coordinates'],'distance_from_source_m':math.dist(xy,expected)},ensure_ascii=False))
for rows in [[base,replace(base,lat=49.8)],[replace(base,lat=49.8),base]]:
    idx=gps.GpsKatasterIndex(rows)
    print(json.dumps({'duplicate_rows_accepted':len(idx.rows),'chosen_lat':idx.by_object_id['OBJ-1'].lat}))
with tempfile.TemporaryDirectory() as td:
    for val in ['nan','inf','91']:
        p=Path(td)/'invalid.csv'; p.write_text('object_id,category,lat,lon\nOBJ-1,jaskinia_otwor,'+val+',19\n')
        idx=gps.load_best_measurements(p)
        print(json.dumps({'input_lat':val,'accepted_lat':str(idx.rows[0].lat)}))
