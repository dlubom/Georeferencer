import copy,importlib.util,json,math,sys,tempfile,subprocess
from pathlib import Path
import yaml
from PIL import Image
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'pipeline'))
spec=importlib.util.spec_from_file_location('gen',ROOT/'pipeline/02_generate_geotiff.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from gps_kataster_coordinates import BestMeasurementRow,GpsKatasterIndex
row=BestMeasurementRow(object_id='TEST',category='jaskinia_otwor',name_local='Test',cave_id='C-1',measurement_id='m-1',lat=49.2,lon=19.0,x_1992='',y_1992='',source='',source_ref='',nr_inwent='',pig_id='',tpn_globalid='',verification_status='')
index=GpsKatasterIndex([row])
meta={'coordinates':{'gps_kataster_object_id':'TEST','lat':'{{ gps_kataster.objects[gps_kataster_object_id].lat }}','lon':'{{ gps_kataster.objects[gps_kataster_object_id].lon }}'},'scale':{'pixels_per_meter':1.0},'north':{'angle_deg':0.0},'entrance':{'x':10.5,'y':20.5},'image':{'width':100,'height':100}}
with tempfile.TemporaryDirectory(prefix='georeferencer-geometry-') as root:
 for case in ('baseline','negative_scale','nan_scale','nan_north','nan_entrance','missing_dimensions','rgb_input'):
  d=Path(root)/case; d.mkdir(); testmeta=copy.deepcopy(meta)
  if case=='negative_scale':testmeta['scale']['pixels_per_meter']=-1.0
  if case=='nan_scale':testmeta['scale']['pixels_per_meter']=float('nan')
  if case=='nan_north':testmeta['north']['angle_deg']=float('nan')
  if case=='nan_entrance':testmeta['entrance']['x']=float('nan')
  if case=='missing_dimensions':testmeta['image']={}
  Image.new('RGB' if case=='rgb_input' else '1',(100,100)).save(d/'image.tif')
  (d/'meta.yaml').write_text(yaml.safe_dump(testmeta))
  try: result=m.process_cave(d,gps_kataster_index=index,gps_kataster_strict=True)
  except Exception as e:result=(False,str(e))
  info=subprocess.run(['gdalinfo','-json',str(d/'image_georef.tif')],capture_output=True,text=True)
  try:infodata=json.loads(info.stdout)
  except ValueError:infodata={}
  gt=infodata.get('geoTransform'); actual=None
  if gt:
   px,py=testmeta['entrance'].values()
   actual=(gt[0]+gt[1]*px+gt[2]*py,gt[3]+gt[4]*px+gt[5]*py)
  expected=m.TRANSFORMER.transform(row.lon,row.lat)
  print(json.dumps({'case':case,'process_result':result,'gt':gt,'click_projected':actual,'expected':expected,'image_exists':(d/'image_georef.tif').exists(),'tfw':(d/'image.tfw').read_text() if (d/'image.tfw').exists() else None,'next_changed_count':len(m.find_caves(Path(root),changed_only=True))},ensure_ascii=False))
