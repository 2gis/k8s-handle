import os
import yaml
import shutil
import unittest
from k8s_handle import settings
from k8s_handle import config
from k8s_handle import templating
from k8s_handle.templating import TemplateRenderingError


class TestTemplating(unittest.TestCase):
    def setUp(self):
        settings.CONFIG_FILE = 'tests/fixtures/config.yaml'
        settings.TEMPLATES_DIR = 'templates/tests'
        os.environ['CUSTOM_ENV'] = 'My value'
        os.environ['K8S_CONFIG_DIR'] = '/tmp/kube/'

    def tearDown(self):
        if os.path.exists(settings.TEMP_DIR):
            shutil.rmtree(settings.TEMP_DIR)

        os.environ.pop('CUSTOM_ENV')
        os.environ.pop('K8S_CONFIG_DIR')

    def test_renderer_init(self):
        r = templating.Renderer('/tmp/test')
        self.assertEqual(r._templates_dir, '/tmp/test')

    def test_none_context(self):
        r = templating.Renderer('templates')
        with self.assertRaises(RuntimeError) as context:
            r.generate_by_context(None)
        self.assertTrue('Can\'t generate templates from None context' in str(context.exception), str(context.exception))

    def test_generate_templates(self):
        r = templating.Renderer(os.path.join(os.path.dirname(__file__), 'templates_tests'))
        context = config.load_context_section('test_dirs')
        r.generate_by_context(context)
        file_path_1 = '{}/template1.yaml'.format(settings.TEMP_DIR)
        file_path_2 = '{}/template2.yaml'.format(settings.TEMP_DIR)
        file_path_3 = '{}/template3.yaml'.format(settings.TEMP_DIR)
        file_path_4 = '{}/innerdir/template1.yaml'.format(settings.TEMP_DIR)
        file_path_5 = '{}/template_include_file.yaml'.format(settings.TEMP_DIR)
        file_path_6 = '{}/template_list_files.yaml'.format(settings.TEMP_DIR)
        self.assertTrue(os.path.exists(file_path_1))
        self.assertTrue(os.path.exists(file_path_2))
        self.assertTrue(os.path.exists(file_path_3))
        with open(file_path_1, 'r') as f:
            content = f.read()
        self.assertEqual(content, "{'ha_ha': 'included_var'}")
        with open(file_path_2, 'r') as f:
            content = f.read()
        self.assertEqual(content, 'TXkgdmFsdWU=')
        with open(file_path_3, 'r') as f:
            content = f.read()
        self.assertEqual(content, 'My value')
        with open(file_path_4, 'r') as f:
            content = f.read()
        self.assertEqual(content, "{'ha_ha': 'included_var'}")
        with open(file_path_5, 'r') as f:
            content = f.read()
        self.assertEqual(content, "test: |\n  {{ hello world }}\n  new\n  line\n  {{ hello world1 }}\n")
        with open(file_path_6, 'r') as f:
            content = f.read()
        self.assertEqual(content, "test: |\n  template1.yaml.j2:\n  my_file.txt:\n  my_file1.txt:\n  ")

    def test_no_templates_in_kubectl(self):
        r = templating.Renderer(os.path.join(os.path.dirname(__file__), 'templates_tests'))
        with self.assertRaises(RuntimeError) as context:
            r.generate_by_context(config.load_context_section('no_templates'))
        self.assertTrue('Templates section doesn\'t have any template items' in str(context.exception))

    def test_render_not_existent_template(self):
        r = templating.Renderer(os.path.join(os.path.dirname(__file__), 'templates_tests'))
        with self.assertRaises(TemplateRenderingError) as context:
            r.generate_by_context(config.load_context_section('not_existent_template'))
        self.assertTrue('doesnotexist.yaml.j2' in str(context.exception), context.exception)

    def test_generate_templates_with_kubectl_section(self):
        r = templating.Renderer(os.path.join(os.path.dirname(__file__), 'templates_tests'))
        context = config.load_context_section('section_with_kubectl')
        r.generate_by_context(context)
        file_path_1 = '{}/template1.yaml'.format(settings.TEMP_DIR)
        file_path_2 = '{}/template2.yaml'.format(settings.TEMP_DIR)
        file_path_3 = '{}/template3.yaml'.format(settings.TEMP_DIR)
        file_path_4 = '{}/innerdir/template1.yaml'.format(settings.TEMP_DIR)
        self.assertTrue(os.path.exists(file_path_1))
        self.assertTrue(os.path.exists(file_path_2))
        self.assertTrue(os.path.exists(file_path_3))
        with open(file_path_1, 'r') as f:
            content = f.read()
        self.assertEqual(content, "{'ha_ha': 'included_var'}")
        with open(file_path_2, 'r') as f:
            content = f.read()
        self.assertEqual(content, 'TXkgdmFsdWU=')
        with open(file_path_3, 'r') as f:
            content = f.read()
        self.assertEqual(content, 'My value')
        with open(file_path_4, 'r') as f:
            content = f.read()
        self.assertEqual(content, "{'ha_ha': 'included_var'}")

    def test_io_2709(self):
        r = templating.Renderer(os.path.join(os.path.dirname(__file__), 'templates_tests'))
        with self.assertRaises(TemplateRenderingError) as context:
            c = config.load_context_section('io_2709')
            r.generate_by_context(c)
        self.assertTrue('due to: \'undefined_variable\' is undefined' in str(context.exception))

    def test_evaluate_tags(self):
        r = templating.Renderer(os.path.join(os.path.dirname(__file__), 'templates_tests'))
        tags = {'tag1', 'tag2', 'tag3'}
        self.assertTrue(r._evaluate_tags(tags, only_tags=['tag1'], skip_tags=None))
        self.assertFalse(r._evaluate_tags(tags, only_tags=['tag4'], skip_tags=None))
        self.assertFalse(r._evaluate_tags(tags, only_tags=['tag1'], skip_tags=['tag1']))
        self.assertFalse(r._evaluate_tags(tags, only_tags=None, skip_tags=['tag1']))
        self.assertTrue(r._evaluate_tags(tags, only_tags=None, skip_tags=['tag4']))
        tags = set()
        self.assertFalse(r._evaluate_tags(tags, only_tags=['tag4'], skip_tags=None))
        self.assertTrue(r._evaluate_tags(tags, only_tags=None, skip_tags=['tag4']))

    def test_get_template_tags(self):
        r = templating.Renderer(os.path.join(os.path.dirname(__file__), 'templates_tests'))
        template_1 = {'template': 'template.yaml.j2', 'tags': ['tag1', 'tag2', 'tag3']}
        template_2 = {'template': 'template.yaml.j2', 'tags': 'tag1,tag2,tag3'}
        template_3 = {'template': 'template.yaml.j2', 'tags': ['tag1']}
        template_4 = {'template': 'template.yaml.j2', 'tags': 'tag1'}
        self.assertEqual(r._get_template_tags(template_1), {'tag1', 'tag2', 'tag3'})
        self.assertEqual(r._get_template_tags(template_2), {'tag1', 'tag2', 'tag3'})
        self.assertEqual(r._get_template_tags(template_3), {'tag1'})
        self.assertEqual(r._get_template_tags(template_4), {'tag1'})

    def test_get_template_tags_unexpected_type(self):
        r = templating.Renderer(os.path.join(os.path.dirname(__file__), 'templates_tests'))
        template = {'template': 'template.yaml.j2', 'tags': {'tag': 'unexpected'}}
        with self.assertRaises(TypeError) as context:
            r._get_template_tags(template)
        self.assertTrue('unexpected type' in str(context.exception))

    def test_generate_group_templates(self):
        r = templating.Renderer(os.path.join(os.path.dirname(__file__), 'templates_tests'))
        context = config.load_context_section('test_groups')
        r.generate_by_context(context)
        file_path_1 = '{}/template1.yaml'.format(settings.TEMP_DIR)
        file_path_2 = '{}/template2.yaml'.format(settings.TEMP_DIR)
        file_path_3 = '{}/template3.yaml'.format(settings.TEMP_DIR)
        self.assertTrue(os.path.exists(file_path_1))
        self.assertTrue(os.path.exists(file_path_2))
        self.assertTrue(os.path.exists(file_path_3))

    def test_templates_regex(self):
        r = templating.Renderer(os.path.join(os.path.dirname(__file__), 'templates_tests'))
        context = config.load_context_section('templates_regex')
        file_path_1 = '{}/template1.yaml'.format(settings.TEMP_DIR)
        file_path_2 = '{}/template2.yaml'.format(settings.TEMP_DIR)
        file_path_3 = '{}/template3.yaml'.format(settings.TEMP_DIR)
        file_path_4 = '{}/template4.yaml'.format(settings.TEMP_DIR)
        file_path_5 = '{}/innerdir/template1.yaml'.format(settings.TEMP_DIR)
        file_path_6 = '{}/template_include_file.yaml'.format(settings.TEMP_DIR)
        r.generate_by_context(context)
        self.assertTrue(os.path.exists(file_path_1))
        self.assertFalse(os.path.exists(file_path_2))
        self.assertFalse(os.path.exists(file_path_3))
        self.assertFalse(os.path.exists(file_path_4))
        self.assertTrue(os.path.exists(file_path_5))
        self.assertFalse(os.path.exists(file_path_6))

    def test_templates_regex_parse_failed(self):
        r = templating.Renderer(os.path.join(os.path.dirname(__file__), 'templates_tests'))
        c = config.load_context_section('templates_regex_invalid')
        with self.assertRaises(TemplateRenderingError) as context:
            r.generate_by_context(c)
        self.assertTrue('Processing [: template [ hasn\'t been found' in str(context.exception))

    def test_filters(self):
        r = templating.Renderer(os.path.join(os.path.dirname(__file__), 'templates_tests'))
        context = config.load_context_section('test_filters')
        r.generate_by_context(context)
        result = '{}/filters.yaml'.format(settings.TEMP_DIR)
        with open(result, 'r') as f:
            actual = yaml.safe_load(f)
        self.assertEqual('aGVsbG8gd29ybGQ=', actual.get('b64encode'))
        self.assertEqual('k8s-handle', actual.get('b64decode'))
        self.assertEqual('8fae6dd899aace000fd494fd6d795e26e2c85bf8e59d4262ef56b03dc91e924c', actual.get('sha256'))
        affinity = [
            {'effect': 'NoSchedule', 'key': 'dedicated', 'operator': 'Equal', 'value': 'monitoring'},
            {'effect': 'NoSchedule', 'key': 'dedicated', 'operator': 'Equal', 'value': {'hello': 'world'}}
        ]
        self.assertEqual(affinity, actual.get('affinity'))
