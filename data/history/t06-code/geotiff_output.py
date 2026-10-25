"""T04: kontrola rzeczywistego GeoTIFF i publikacja całego przebiegu.

Tylko dowiązanie current jest punktem publikacji. Dane źródłowe są odczytywane;
niezakończony staging nigdy nie zastępuje poprzedniego kompletu.
"""
import hashlib
import json
import math
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from PIL import Image
from pyproj import CRS
from pyproj.exceptions import CRSError

from coordinate_source import sha256


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


def input_files(cave_dir):
    """Źródłowy YAML i obrazy; stary TFW/GeoTIFF nie są wejściem obliczeń."""
    return [p for p in sorted(cave_dir.iterdir()) if p.is_file() and
            (p.name == 'meta.yaml' or (p.suffix.lower() in {'.tif', '.tiff', '.jpg', '.jpeg', '.png'}
                                      and p.name != 'image_georef.tif'))]


def input_hashes(cave_dir):
    return {p.name: sha256(p) for p in input_files(cave_dir)}


def guard_input_path(path, output):
    """Sprawdź każdy krok, również symlink przez current do pliku poza output.

    Sam końcowy resolve() gubi takie przejście i podmiana current mogłaby
    zmienić źródło. Rozwiązujemy komponenty przed obsługą kolejnego '..'.
    """
    path = Path(path)
    if not path.is_absolute():
        path = Path.cwd() / path
    pending = list(path.parts[1:])
    resolved = Path(path.anchor)
    links = 0
    while pending:
        part = pending.pop(0)
        if part == '..':
            resolved = resolved.parent
            continue
        resolved = resolved / part
        if resolved == output or output in resolved.parents:
            raise ValueError(f'Katalog wyników występuje na ścieżce wejścia: {path}')
        if resolved.is_symlink():
            links += 1
            if links > 40:
                raise ValueError(f'Za dużo dowiązań na ścieżce wejścia: {path}')
            target = resolved.readlink()
            resolved = Path(target.anchor) if target.is_absolute() else resolved.parent
            pending = list(target.parts[1:] if target.is_absolute() else target.parts) + pending


def validate_output_dir(output_dir, data_dir, caves, protected_files=()):
    output = Path(output_dir).resolve()
    for source in [Path(data_dir).resolve(), *(Path(c).resolve() for c in caves)]:
        if output == source or source in output.parents or output in source.parents:
            raise ValueError('Katalog wyników nie może nakładać się na źródłowy katalog danych')
    for path in [*protected_files, *(p for cave in caves for p in input_files(cave))]:
        guard_input_path(path, output)
    # Nie przejmujemy istniejącego katalogu/pliku o nazwie current.
    current = output / 'current'
    if current.exists() and not current.is_symlink():
        raise ValueError('Katalog wyników: current musi być dowiązaniem do przebiegu')
    if (output / 'runs').is_symlink():
        raise ValueError('Katalog wyników: runs nie może być dowiązaniem')
    return output


def tfw_geotransform(tfw_path):
    """TFW: środek pierwszego piksela → GDAL: narożnik, z precyzją zapisu TFW.

    Kliknięcia UI mają układ narożnikowy GDAL. C,F generatora T06 już
    uwzględniają przesunięcie do środka; tutaj zachowujemy konwersję GDAL.
    """
    a, d, b, e, c, f = map(float, tfw_path.read_text().splitlines())
    return [c - a * 0.5 - b * 0.5, a, b, f - d * 0.5 - e * 0.5, d, e]


def translate_geotiff(source, output, transform):
    result = subprocess.run([
        'gdal_translate', '-of', 'GTiff', '-a_srs', 'EPSG:2180',
        '-a_gt', *(str(v) for v in transform),
        '-co', 'COMPRESS=CCITTFAX4', str(source), str(output),
    ], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f'gdal_translate: {result.stderr.strip()}')


def decoded_pixels(path):
    """Hash zdekodowanych wierszy, bez metadanych i sposobu kompresji TIFF."""
    digest = hashlib.sha256()
    with Image.open(path) as image:
        # GDAL zapisuje także 1-bit TIFF z paletą; Pillow odczytuje go jako P.
        if image.tag_v2.get(258, (1,)) != (1,) or getattr(image, 'n_frames', 1) != 1:
            raise ValueError('GeoTIFF: wymagany pojedynczy obraz 1-bit')
        image.load()  # wymusza także wykrycie uszkodzonego strumienia
        size = image.size
        for top in range(0, image.height, 256):
            with image.crop((0, top, image.width, min(top + 256, image.height))) as rows:
                digest.update(rows.convert('L').tobytes())
    return size, digest.hexdigest()


def check_geotiff(source, output, expected_transform):
    """Kod wyjścia GDAL nie zastępuje niezależnego odczytu i porównania."""
    result = subprocess.run(['gdalinfo', '-json', str(output)], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f'GeoTIFF: kontrolny odczyt gdalinfo: {result.stderr.strip()}')
    try:
        info = json.loads(result.stdout)
        if info['driverShortName'] != 'GTiff':
            raise ValueError('GeoTIFF: wymagany format GTiff')
        if CRS.from_wkt(info['coordinateSystem']['wkt']).to_epsg() != 2180:
            raise ValueError('GeoTIFF: CRS musi być EPSG:2180')
        transform = info['geoTransform']
        if len(transform) != 6 or not all(math.isfinite(v) for v in transform):
            raise ValueError('GeoTIFF: transformacja musi być skończona')
        determinant = transform[1] * transform[5] - transform[2] * transform[4]
        if not math.isfinite(determinant) or determinant == 0:
            raise ValueError('GeoTIFF: transformacja musi być odwracalna')
        if any(not math.isclose(a, b, rel_tol=0, abs_tol=1e-9)
               for a, b in zip(transform, expected_transform)):
            raise ValueError('GeoTIFF: transformacja inna niż bieżące obliczenie')
        if (len(info['bands']) != 1 or
                info['metadata']['IMAGE_STRUCTURE']['COMPRESSION'] != 'CCITTFAX4'):
            raise ValueError('GeoTIFF: wymagany jeden kanał i kompresja CCITTFAX4')
    except (KeyError, TypeError, json.JSONDecodeError, CRSError) as exc:
        raise ValueError(f'GeoTIFF: niepełny kontrolny odczyt: {exc}') from exc
    source_size, source_pixels = decoded_pixels(source)
    output_size, output_pixels = decoded_pixels(output)
    if source_size != output_size or info['size'] != list(source_size):
        raise ValueError('GeoTIFF: wymiary inne niż obraz źródłowy')
    if source_pixels != output_pixels:
        raise ValueError('GeoTIFF: zdekodowane piksele inne niż obraz źródłowy')
    return {'crs': 'EPSG:2180', 'geotransform': transform,
            'size': list(output_size), 'decoded_pixels_sha256': output_pixels}


def publish_run(output_dir, plans, provenance, write_tfw):
    """Zapisz i sprawdź całą partię, potem atomowo opublikuj current.

    plans zawiera zwalidowane dane oraz hashe sprzed preflightu.
    write_tfw to wspólny serializer przejściowego i nowego trybu.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    runs = output_dir / 'runs'
    runs.mkdir(exist_ok=True)
    run_id = uuid.uuid4().hex
    staging = output_dir / ('.staging-' + run_id)
    destination = runs / run_id
    pointer = output_dir / ('.current-' + run_id)
    staging.mkdir()
    published = False
    try:
        records = []
        for plan in plans:
            cave_dir = plan['source_directory']
            if input_hashes(cave_dir) != plan['inputs']:
                raise ValueError(f'plan {cave_dir.name}: wejścia zmieniły się podczas generacji')
            target = staging / cave_dir.name
            target.mkdir()
            tfw_path = write_tfw(target, plan['params'])
            transform = tfw_geotransform(tfw_path)
            output = target / 'image_georef.tif'
            # GDAL i odczyt pikseli otrzymują tę samą kopię sprawdzoną hashem T03.
            # Połączenie bezpośrednio ze zmiennym źródłem zostawiałoby wyścig A→B→A.
            snapshot = target / '.input.tif'
            shutil.copyfile(cave_dir / 'image.tif', snapshot)
            if sha256(snapshot) != plan['inputs']['image.tif']:
                raise ValueError(f'plan {cave_dir.name}: obraz zmienił się podczas kopiowania')
            translate_geotiff(snapshot, output, transform)
            acceptance = check_geotiff(snapshot, output, transform)
            snapshot.unlink()
            write_json(target / 'computed.json', plan['computed'])
            records.append({
                'dir_id': cave_dir.name, 'source_directory': str(cave_dir.resolve()),
                'inputs': plan['inputs'], 'measurement': plan['measurement'],
                'parameters': plan['params'], 'orientation': plan['orientation'], 'acceptance': acceptance,
                'outputs': {p.name: sha256(p) for p in sorted(target.iterdir())},
            })
        # Weryfikacja także wcześniejszych planów i wspólnych źródeł po całej partii.
        for plan in plans:
            if input_hashes(plan['source_directory']) != plan['inputs']:
                raise ValueError('Wejścia zmieniły się podczas generacji')
        for path, digest in provenance['guarded_files'].items():
            if sha256(path) != digest:
                raise ValueError(f'Wejście zmieniło się podczas generacji: {path}')
        manifest = {key: value for key, value in provenance.items() if key != 'guarded_files'}
        manifest.update(schema_version=1, status='complete', run_id=run_id, plans=records)
        write_json(staging / 'manifest.json', manifest)
        os.replace(staging, destination)
        pointer.symlink_to(Path('runs') / run_id, target_is_directory=True)
        os.replace(pointer, output_dir / 'current')
        published = True
        return destination
    finally:
        if pointer.is_symlink():
            pointer.unlink()
        if staging.exists():
            shutil.rmtree(staging)
        if not published and destination.exists():
            shutil.rmtree(destination)
