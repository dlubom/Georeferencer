import importlib.util,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'pipeline'))
spec=importlib.util.spec_from_file_location('gen',ROOT/'pipeline/02_generate_geotiff.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from pyproj import Proj
for lat,lon in [(49.2,19.9),(49.2,19.0),(49.2,18.1)]:
 meta={'coordinates':{'lat':lat,'lon':lon},'scale':{'pixels_per_meter':1.0},'north':{'angle_deg':0.0},'entrance':{'x':0.0,'y':0.0}}
 p=m.compute_world_file(meta)
 x,y=m.TRANSFORMER.transform(lon,lat); xn,yn=m.TRANSFORMER.transform(lon,lat+0.00001)
 bearing=lambda dx,dy:math.degrees(math.atan2(dx,dy))
 true_angle=bearing(xn-x,yn-y)
 output_angle=bearing(-p['B'],-p['E'])
 print({'coordinate':(lat,lon),'true_north_bearing_in_2180':true_angle,'generated_north_arrow_bearing':output_angle,'error_deg':output_angle-true_angle,'error_1km_m':2*1000*math.sin(math.radians(abs(output_angle-true_angle))/2),'proj_convergence':Proj('EPSG:2180').get_factors(lon,lat).meridian_convergence})
