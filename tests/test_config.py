import os
import shutil
import unittest
import settings
import config
from config import InvalidYamlException
from config import get_client_config


class TestContextGeneration(unittest.TestCase):
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

    def test_config_not_exist(self):
        settings.CONFIG_FILE = 'tests/config.yaml'
        with self.assertRaises(Exception) as context:
            config.load_context_section('section')
        self.assertTrue('No such file or directory: \'tests/config.yaml\'' in str(context.exception))

    def test_config_is_empty(self):
        settings.CONFIG_FILE = 'tests/fixtures/empty_config.yaml'
        with self.assertRaises(RuntimeError) as context:
            config.load_context_section('section')
        self.assertTrue('Config file "tests/fixtures/empty_config.yaml" is empty' in str(context.exception))

    def test_config_incorrect(self):
        settings.CONFIG_FILE = 'tests/fixtures/incorrect_config.yaml'
        with self.assertRaises(InvalidYamlException):
            config.load_context_section('section')

    def test_not_existed_section(self):
        with self.assertRaises(RuntimeError) as context:
            config.load_context_section('absent_section')
        self.assertTrue('Section "absent_section" not found' in str(context.exception))

    def test_no_templates(self):
        with self.assertRaises(RuntimeError) as context:
            config.load_context_section('no_templates_section')
        self.assertTrue('Section "templates" or "kubectl" not found in config file' in str(context.exception))

    def test_common_section(self):
        with self.assertRaises(RuntimeError) as context:
            config.load_context_section(settings.COMMON_SECTION_NAME)
        self.assertTrue('Section "{}" is not intended to deploy'.format(
            settings.COMMON_SECTION_NAME) in str(context.exception))

    def test_merge_section_options(self):
        settings.TEMPLATES_DIR = 'templates_tests'
        c = config.load_context_section('test_dirs')
        self.assertEqual(c['my_var'], 'my_value')
        self.assertEqual(c['my_env_var'], 'My value')
        self.assertEqual(c['my_file'],
                         {'ha_ha': 'included_var'})
        self.assertTrue(c['dirs'])

    def test_recursive_vars(self):
        settings.TEMPLATES_DIR = 'templates_tests'
        c = config.load_context_section('test_recursive_vars')
        self.assertEqual({'router': {
            'my': 'var',
            'my1': 'var1',
            'your': 2
        }}, c['var'])

    def test_concatination_with_env(self):
        settings.TEMPLATES_DIR = 'templates_tests'
        c = config.load_context_section('test_dirs')
        self.assertEqual(c['my_conc_env_var1'],
                         'prefix-My value-postfix')
        self.assertEqual(c['my_conc_env_var2'],
                         'prefix-My value')
        self.assertEqual(c['my_conc_env_var3'],
                         'My value-postfix')

    def test_dashes_in_var_names(self):
        settings.TEMPLATES_DIR = 'templates_tests'
        settings.CONFIG_FILE = 'tests/fixtures/dashes_config.yaml'
        with self.assertRaises(RuntimeError) as context:
            config.load_context_section('section')
        self.assertTrue('Variable names should never include dashes, '
                        'check your vars, please: my-nested-var, my-var, your-var'
                        in str(context.exception), context.exception)

    def test_context_update_recursion(self):
        my_dict = {
            'section1': {
                'subsection1': {
                    'section1-key1': 'value',
                    'section1-key2': 1,
                    'section1-key3': 0.1,
                    'section1-key4': [0, 1, 2, 3],
                    'section1-key5': "{{ env='CUSTOM_ENV' }}",
                    'section1-key6': "{{ file='tests/fixtures/include.yaml' }}",
                }
            },
            'section2': [
                {},
                'var2',
                'var3',
                '{{ env=\'CUSTOM_ENV\' }}'
            ],
            'section3': [0, 1, 2, 3, 4]
        }
        expected_dict = {
            'section1': {
                'subsection1': {
                    'section1-key1': 'value',
                    'section1-key2': 1,
                    'section1-key3': 0.1,
                    'section1-key4': [0, 1, 2, 3],
                    'section1-key5': 'My value',
                    'section1-key6': {'ha_ha': 'included_var'},
                }
            },
            'section2': [
                {},
                'var2',
                'var3',
                'My value'
            ],
            'section3': [0, 1, 2, 3, 4]
        }
        self.assertDictEqual(expected_dict, config._update_context_recursively(my_dict))

    def test_context_update_section(self):
        output = config._update_context_recursively('123')
        self.assertEqual('123', output)

    def test_env_var_in_section1_dont_set(self):
        settings.CONFIG_FILE = 'tests/fixtures/config_with_env_vars.yaml'
        settings.GET_ENVIRON_STRICT = True
        with self.assertRaises(RuntimeError) as context:
            config.load_context_section('section-1')

        settings.GET_ENVIRON_STRICT = False
        self.assertTrue('Environment variable "SECTION1" is not set'
                        in str(context.exception))

    def test_env_var_in_section2_dont_set(self):
        settings.CONFIG_FILE = 'tests/fixtures/config_with_env_vars.yaml'
        settings.GET_ENVIRON_STRICT = True
        with self.assertRaises(RuntimeError) as context:
            config.load_context_section('section-2')

        settings.GET_ENVIRON_STRICT = False
        self.assertTrue('Environment variable "SECTION2" is not set' in str(context.exception))

    def test_env_var_in_include_dont_set(self):
        settings.CONFIG_FILE = 'tests/fixtures/config_with_include_and_env_vars.yaml'
        settings.GET_ENVIRON_STRICT = True
        with self.assertRaises(RuntimeError):
            config.load_context_section('section-2')

        settings.GET_ENVIRON_STRICT = False

    def test_env_var_in_include_2_levels_dont_set(self):
        settings.CONFIG_FILE = 'tests/fixtures/config_with_include_and_env_vars.yaml'
        settings.GET_ENVIRON_STRICT = True
        with self.assertRaises(RuntimeError):
            config.load_context_section('section-1')

        settings.GET_ENVIRON_STRICT = False

    def test_infinite_recursion_loop(self):
        settings.CONFIG_FILE = 'tests/fixtures/config_with_include_and_env_vars.yaml'
        with self.assertRaises(RuntimeError):
            config.load_context_section('section-3')

    def test_get_client_config(self):
        context = {
            'k8s_master_uri': 'http://test.test/',
            'k8s_ca_base64': 'Q0EK',
            'k8s_token': 'token',
        }
        client = get_client_config(context)
        self.assertFalse(client.debug)
        self.assertEqual(client.host, 'http://test.test/')
        with open(client.ssl_ca_cert) as f:
            self.assertEqual(f.read(), 'CA\n')
        self.assertEqual(client.api_key, {'authorization': 'Bearer token'})

        context['k8s_handle_debug'] = ''
        self.assertFalse(get_client_config(context).debug)
        context['k8s_handle_debug'] = '1'
        self.assertFalse(get_client_config(context).debug)
        context['k8s_handle_debug'] = 'False'
        self.assertFalse(get_client_config(context).debug)
        context['k8s_handle_debug'] = 'false'
        self.assertFalse(get_client_config(context).debug)

        context['k8s_handle_debug'] = 'true'
        self.assertTrue(get_client_config(context).debug)
        context['k8s_handle_debug'] = 'True'
        self.assertTrue(get_client_config(context).debug)

    def test_check_k8s_settings(self):
        settings.CONFIG_FILE = 'tests/fixtures/config_without_k8s.yaml'
        c = config.load_context_section('deployment')
        with self.assertRaises(RuntimeError) as context:
            config.check_required_vars(c, ['k8s_master_uri', 'k8s_token', 'k8s_ca_base64', 'k8s_namespace'])
        self.assertTrue('Variables "k8s_token, k8s_ca_base64" not found '
                        '(or empty)' in str(context.exception), )

    def test_check_empty_var(self):
        settings.CONFIG_FILE = 'tests/fixtures/config.yaml'
        settings.GET_ENVIRON_STRICT = True
        with self.assertRaises(RuntimeError) as context:
            config.load_context_section('deployment')
        settings.GET_ENVIRON_STRICT = False
        self.assertTrue('Environment variable "EMPTY_ENV" is not set'
                        in str(context.exception))
