"""T09: egzekwowanie QA, dane źródłowe i rzeczywiste wyniki T04."""
import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

import yaml
import test_gdal_smoke as fixture
from test_geotiff_output import generator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
spec = importlib.util.spec_from_file_location('t09_report', ROOT / 'pipeline/03_report.py')
report_cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report_cli)


class _QaFixture(unittest.TestCase):
    def setUp(self):
        fixture.GdalSmokeTest.setUp(self)
        self.assertTrue(hasattr(report_cli, 'create_report'), 'Brak bieżącego QA i rejestru wyjątków')
        self.data = self.data_dir
        self.output = self.data / '_results'

    def report(self, **kwargs):
        return report_cli.create_report(self.data, registry_path=self.registry_path,
            aggregates={}, observations=[], exceptions={'schema_version': 1, 'exceptions': []}, **kwargs)

    def rules(self, report):
        return {p['rule'] for p in report['problems']}

    def exception(self, report, rule):
        problem = next(p for p in report['problems'] if p['rule'] == rule)
        return {'plan_id': problem['plan_id'], 'rule': rule, 'basis_sha256': problem['basis_sha256'],
                'evidence': problem['evidence'], 'reason': 'Znana niepewność próby T09',
                'close_when': 'Po ręcznym sprawdzeniu konkretnego źródła', 'sources': ['synthetic:test_qa']}

    def with_exceptions(self, entries, **kwargs):
        return report_cli.create_report(self.data, registry_path=self.registry_path,
            aggregates={}, observations=[], exceptions={'schema_version': 1, 'exceptions': entries}, **kwargs)



class QaTest(_QaFixture):
    def test_clean_checkout_has_sources_without_generated_results(self):
        result = self.report()
        self.assertEqual(len(result['plans']), 1)
        self.assertEqual(result['plans'][0]['input_status'], 'valid')
        self.assertEqual(result['plans'][0]['output_status'], 'not_requested')
        self.assertNotIn('input.missing', self.rules(result))
        self.assertIn('orientation.unknown', self.rules(result))

    def test_specific_exception_passes_but_new_rule_and_stale_basis_block(self):
        first = self.report()
        known = self.exception(first, 'orientation.unknown')
        self.assertTrue(self.with_exceptions([known])['passed'])
        meta = yaml.safe_load(self.meta_path.read_text())
        meta['quality'] = {'ppm_cv': .2, 'entrance_std_px': 11, 'flag': None}
        self.meta_path.write_text(yaml.safe_dump(meta))
        changed = self.with_exceptions([known])
        self.assertFalse(changed['passed'])
        self.assertIn('exception.stale', self.rules(changed))
        self.assertTrue({'scale.disagreement', 'entrance.disagreement'} <= self.rules(changed))
        renewed = self.exception(changed, 'orientation.unknown')
        self.assertFalse(self.with_exceptions([renewed])['passed'])

    def test_technical_fault_cannot_be_excepted(self):
        self.meta_path.write_text(self.meta_path.read_text().replace('pixels_per_meter: 2.0', 'pixels_per_meter: 0.0'))
        result = self.report()
        self.assertIn('input.invalid', self.rules(result))
        technical = self.exception(result, 'input.invalid')
        self.assertFalse(self.with_exceptions([technical])['passed'])
        self.assertIn('exception.invalid', self.rules(self.with_exceptions([technical])))

    def test_directory_without_yaml_is_not_silently_dropped(self):
        (self.data / 'another-plan').mkdir()
        result = self.report()
        self.assertEqual(len(result['plans']), 2)
        self.assertIn('input.missing', self.rules(result))

    def test_selected_run_is_complete_then_stale_even_with_new_mtime(self):
        # Wyniki muszą leżeć poza źródłami.
        output = self.data.parent / (self.data.name + '-results')
        self.addCleanup(lambda: __import__('shutil').rmtree(output, ignore_errors=True))
        run = generator.process_output([self.cave_dir], output, self.data, self.coordinates_path, self.registry_path)
        result = self.report(run_dir=run)
        self.assertEqual(result['plans'][0]['output_status'], 'current')
        self.assertNotIn('result.corrupt', self.rules(result))
        self.meta_path.write_text(self.meta_path.read_text() + '# zmiana wejścia\n')
        __import__('os').utime(run / '001131/image_georef.tif', None)
        result = self.report(run_dir=run)
        self.assertEqual(result['plans'][0]['output_status'], 'stale')
        self.assertIn('result.stale', self.rules(result))

    def test_selected_run_missing_corrupt_extra_and_duplicate_are_technical(self):
        output = self.data.parent / (self.data.name + '-results')
        self.addCleanup(lambda: __import__('shutil').rmtree(output, ignore_errors=True))
        run = generator.process_output([self.cave_dir], output, self.data, self.coordinates_path, self.registry_path)
        tif = run / '001131/image_georef.tif'
        raw = tif.read_bytes()
        tif.unlink()
        self.assertIn('result.missing', self.rules(self.report(run_dir=run)))
        tif.write_bytes(b'broken')
        self.assertIn('result.corrupt', self.rules(self.report(run_dir=run)))
        tif.write_bytes(raw)
        (run / 'extra').write_text('unexpected')
        self.assertIn('result.inventory', self.rules(self.report(run_dir=run)))
        (run / 'extra').unlink()
        manifest_path = run / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['plans'].append(copy.deepcopy(manifest['plans'][0]))
        manifest_path.write_text(json.dumps(manifest))
        self.assertIn('result.inventory', self.rules(self.report(run_dir=run)))

    def test_required_results_missing_is_distinct_from_missing_input(self):
        result = self.report(require_results=True)
        self.assertIn('result.missing', self.rules(result))
        self.assertEqual(result['plans'][0]['input_status'], 'valid')


class CatalogueQaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from qa import create_report
        cls.report = create_report()

    def test_current_catalogue_uses_all_t07_components_and_enforced_exceptions(self):
        actual={p.name for p in (ROOT/'data/caves').iterdir() if p.is_dir() and not p.name.startswith(('_','.'))}
        self.assertEqual({p['plan_id'] for p in self.report['plans']}, actual)
        self.assertEqual(self.report['counts']['plans'], len(actual))
        self.assertEqual(sum(self.report['counts']['origins'].values()),len(actual))
        self.assertTrue(self.report['passed'], self.report['counts'])
        plans = {p['plan_id']: p for p in self.report['plans']}
        self.assertEqual(sum((p['components'] or {}).get('north', {}).get('observations', 0) for p in plans.values()), 1717)
        self.assertEqual(plans['001094']['components']['north']['observations'], 5)
        self.assertEqual(plans['001094']['link_status'], 'explicit_valid_pending_review')
        self.assertNotIn('entrance.disagreement', plans['001094']['problems'])
        self.assertEqual(plans['001050']['north_measurements']['angle_deg'], None)
        self.assertEqual(plans['001230']['north_measurements']['angle_deg'], 0)
        self.assertTrue(all(p['orientation']['status'] == 'unverified' for p in plans.values()))

    def test_repeated_reports_are_byte_identical_and_issues_stay_sourced(self):
        import tempfile
        from qa import create_report, write_reports
        again = create_report()
        self.assertEqual(self.report, again)
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / 'first', Path(tmp) / 'second'
            write_reports(self.report, first)
            write_reports(again, second)
            self.assertEqual({p.name: p.read_bytes() for p in first.iterdir()},
                             {p.name: p.read_bytes() for p in second.iterdir()})
        reconciliation = self.report['issue_reconciliation']
        self.assertEqual(len([r for r in reconciliation if r['source'].endswith('/3')]), 6)
        self.assertTrue(all(r['source'].startswith('https://github.com/dlubom/Georeferencer/issues/') for r in reconciliation))
        self.assertTrue(any(r['status'] == 'unmatched_name_or_id' for r in reconciliation))


class ManualQaTest(unittest.TestCase):
    def test_t08_models_local_identity_and_zero_are_distinct(self):
        from test_manual_add import ManualAddTest
        from qa import create_report
        helper = ManualAddTest()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        for reference in ('unknown', 'grid', 'geographic', 'magnetic'):
            helper.add(reference=reference, plan_id='manual-' + reference)
        result = create_report(helper.data, aggregates={}, observations=[],
                               exceptions={'schema_version':1,'exceptions':[]})
        self.assertEqual(len(result['plans']), 4)
        self.assertTrue(all(p['origin'] == 'manual_t08' and p['input_status'] == 'valid' for p in result['plans']))
        plans = {p['plan_id']:p for p in result['plans']}
        unknown = plans['manual-unknown']
        self.assertIsNone(unknown['north_angle_deg'])
        self.assertEqual(unknown['orientation']['north_reference'], 'unknown')
        self.assertEqual(unknown['orientation']['mode'], 'assumed_grid')
        self.assertEqual(plans['manual-grid']['north_angle_deg'], 0)
        self.assertEqual(plans['manual-grid']['orientation']['angle_origin'], 'measured')
        # Przyjęte r=0° pozostaje oddzielne od brakującego pomiaru null.
        path=helper.data/'manual-unknown/meta.yaml'
        meta=yaml.safe_load(path.read_text())
        meta['orientation']['grid_assumption']['rotation_deg']=0.0
        from orientation import record_decision
        meta=record_decision(meta,'Jawnie przyjęto zero w próbie QA','2026-10-25')
        path.write_text(yaml.safe_dump(meta))
        result=create_report(helper.data, aggregates={}, observations=[], exceptions={'schema_version':1,'exceptions':[]})
        unknown=next(p for p in result['plans'] if p['plan_id']=='manual-unknown')
        self.assertEqual(unknown['rotation_deg'],0)
        self.assertIsNone(unknown['north_angle_deg'])
        local=helper.data/'manual-grid/image-identity.json'
        local.write_text(local.read_text().replace('image_102','image_101'))
        result=create_report(helper.data, aggregates={}, observations=[], exceptions={'schema_version':1,'exceptions':[]})
        self.assertEqual(next(p for p in result['plans'] if p['plan_id']=='manual-grid')['input_status'],'invalid')
        local.unlink()
        result=create_report(helper.data, aggregates={}, observations=[], exceptions={'schema_version':1,'exceptions':[]})
        self.assertEqual(next(p for p in result['plans'] if p['plan_id']=='manual-grid')['input_status'],'missing')


class RegistryQaTest(_QaFixture):
    def test_malformed_or_unused_exception_is_a_reported_blocker(self):
        for entries in ([{'plan_id': [], 'rule': {}}], [None],
                        [{'plan_id':'missing','rule':'orientation.unknown','basis_sha256':'x',
                          'reason':'r','close_when':'c','sources':['s'],'evidence':{}}]):
            with self.subTest(entries=entries):
                result=self.with_exceptions(entries)
                self.assertFalse(result['passed'])
                self.assertTrue({'exception.invalid','exception.stale'} & self.rules(result))

    def test_changing_only_local_registry_presence_cannot_match_old_result(self):
        output=self.data.parent/(self.data.name+'-results')
        self.addCleanup(lambda: __import__('shutil').rmtree(output,ignore_errors=True))
        run=generator.process_output([self.cave_dir],output,self.data,self.coordinates_path,self.registry_path)
        local=self.cave_dir/'image-identity.json'
        local.write_text(self.registry_path.read_text())
        result=self.report(run_dir=run)
        self.assertIn('input.invalid',self.rules(result))
        self.assertIn('result.stale',self.rules(result))

    def test_manifest_omitted_input_and_wrong_measurement_do_not_pass(self):
        output=self.data.parent/(self.data.name+'-results')
        self.addCleanup(lambda: __import__('shutil').rmtree(output,ignore_errors=True))
        run=generator.process_output([self.cave_dir],output,self.data,self.coordinates_path,self.registry_path)
        path=run/'manifest.json'
        original=path.read_text()
        for field in ('inputs','measurement'):
            manifest=json.loads(original)
            del manifest['plans'][0][field]
            path.write_text(json.dumps(manifest))
            self.assertIn('result.stale',self.rules(self.report(run_dir=run)))


class AdditionalQaTest(_QaFixture):
    def test_north_support_spread_and_multiple_quality_rules_ignore_legacy_flag(self):
        from crowdsourcing import aggregate_cave
        from test_crowdsourcing import row
        from qa import create_report
        rows=[row(i, user='same-user',angle=a,image_id=1,
                  image_used_path='caves_mono/001131/image_1.tif',pixels_per_meter=ppm)
              for i,a,ppm in ((1,0,1),(2,20,2))]
        group=aggregate_cave('T.X-01.01',rows,classification={})
        group['north']['max_pairwise_difference_deg']=20
        group['quality'].update(ppm_cv=.2,entrance_std_px=11,flag=None)
        group['raw'].update(ppm_cv=.2,entrance_std_px=11)
        result=create_report(self.data, registry_path=self.registry_path,
            aggregates={'001131':group},observations=[],exceptions={'schema_version':1,'exceptions':[]})
        self.assertTrue({'north.low_support','north.disagreement','scale.disagreement','entrance.disagreement'} <= self.rules(result))
        self.assertEqual(result['plans'][0]['components']['north']['users'],1)
        self.assertEqual(result['plans'][0]['components']['north']['observations'],2)

    def test_quality_thresholds_use_unrounded_t07_measurements(self):
        from crowdsourcing import aggregate_cave
        from test_crowdsourcing import row
        from qa import create_report
        first=row(1,image_id=1,image_used_path='caves_mono/001131/image_1.tif',pixels_per_meter=.8996)
        second=row(2,image_id=1,image_used_path='caves_mono/001131/image_1.tif',pixels_per_meter=1.1004)
        points=json.loads(second['points_orig_json'])
        points[0]['x']=30.008
        second['points_orig_json']=json.dumps(points)
        group=aggregate_cave('T.X-01.01',[first,second],classification={})
        self.assertEqual(group['quality']['ppm_cv'],.1)
        self.assertEqual(group['quality']['entrance_std_px'],10)
        result=create_report(self.data,registry_path=self.registry_path,aggregates={'001131':group},
            observations=[],exceptions={'schema_version':1,'exceptions':[]})
        self.assertTrue({'scale.disagreement','entrance.disagreement'} <= self.rules(result))

    def test_changed_implementation_and_partial_run_are_not_current(self):
        from unittest.mock import patch
        import qa_outputs
        output=self.data.parent/(self.data.name+'-results')
        self.addCleanup(lambda: __import__('shutil').rmtree(output,ignore_errors=True))
        run=generator.process_output([self.cave_dir],output,self.data,self.coordinates_path,self.registry_path)
        implementation=qa_outputs._implementation()
        implementation['orientation.py']='0'*64
        with patch.object(qa_outputs,'_implementation',return_value=implementation):
            self.assertIn('result.stale',self.rules(self.report(run_dir=run)))
        (self.data/'new-plan').mkdir()
        self.assertIn('result.inventory',self.rules(self.report(run_dir=run)))

    def test_tiff_readback_is_required_even_if_manifest_hash_is_updated(self):
        import hashlib
        import subprocess
        output=self.data.parent/(self.data.name+'-results')
        self.addCleanup(lambda: __import__('shutil').rmtree(output,ignore_errors=True))
        run=generator.process_output([self.cave_dir],output,self.data,self.coordinates_path,self.registry_path)
        original=run/'001131/image_georef.tif'
        bad=run/'001131/bad.tif'
        subprocess.run(['gdal_translate','-a_srs','EPSG:4326','-co','COMPRESS=CCITTFAX4',str(original),str(bad)],check=True,capture_output=True)
        bad.replace(original)
        path=run/'manifest.json'
        manifest=json.loads(path.read_text())
        manifest['plans'][0]['outputs']['image_georef.tif']=hashlib.sha256(original.read_bytes()).hexdigest()
        path.write_text(json.dumps(manifest))
        self.assertIn('result.corrupt',self.rules(self.report(run_dir=run)))

class ReviewQaTest(_QaFixture):
    def test_missing_image_is_missing_input_and_in_missing_csv(self):
        from qa import write_reports
        import csv
        self.image_path.unlink()
        result=self.report()
        self.assertEqual(result['plans'][0]['input_status'],'missing')
        self.assertIn('input.missing',self.rules(result))
        write_reports(result,self.data/'_qa')
        with (self.data/'_qa/missing.csv').open() as stream:
            self.assertEqual(len(list(csv.DictReader(stream))),1)

    def test_missing_shared_registry_is_missing_source(self):
        self.registry_path.unlink()
        result=self.report()
        self.assertEqual(result['plans'][0]['input_status'],'missing')
        self.assertIn('input.missing',self.rules(result))

    def test_malformed_manifest_and_local_identity_are_reported_not_crashes(self):
        (self.cave_dir/'image-identity.json').write_text('[]')
        result=self.report()
        self.assertIn('input.invalid',self.rules(result))
        (self.cave_dir/'image-identity.json').unlink()
        run=self.data/'_run'
        run.mkdir()
        (run/'manifest.json').write_text('[]')
        self.assertIn('result.corrupt',self.rules(self.report(run_dir=run)))


if __name__ == '__main__':
    unittest.main()
