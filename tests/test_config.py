import os
import shutil
import unittest

from k8s_handle import config
from k8s_handle import settings
from k8s_handle.config import KEY_K8S_CA_BASE64
from k8s_handle.config import KEY_K8S_MASTER_URI
from k8s_handle.config import KEY_K8S_NAMESPACE
from k8s_handle.config import KEY_K8S_NAMESPACE_ENV
from k8s_handle.config import KEY_K8S_TOKEN
from k8s_handle.config import KEY_K8S_CA_BASE64_URI_ENV_DEPRECATED
from k8s_handle.config import KEY_K8S_HANDLE_DEBUG
from k8s_handle.config import KEY_K8S_MASTER_URI_ENV_DEPRECATED
from k8s_handle.config import PriorityEvaluator
from k8s_handle.filesystem import InvalidYamlError

VALUE_CLI = 'value_cli'
VALUE_CONTEXT = 'value_context'
VALUE_ENV = 'value_env'
VALUE_ENV_DEPRECATED = 'value_env_deprecated'
VALUE_CA = 'Q0EK'
VALUE_TOKEN = 'token'
KUBECONFIG_NAMESPACE = 'kubeconfig_namespace'


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
        with self.assertRaises(InvalidYamlError):
            config.load_context_section('section')

    def test_not_existed_section(self):
        with self.assertRaises(RuntimeError) as context:
            config.load_context_section('absent_section')
        self.assertTrue('Section "absent_section" not found' in str(context.exception))

    def test_no_templates(self):
        with self.assertRaises(RuntimeError) as context:
            config.load_context_section('no_templates_section')
        self.assertTrue('Section "templates" or "kubectl" not found in config file' in str(context.exception))

    def test_empty_section(self):
        with self.assertRaises(RuntimeError) as context:
            config.load_context_section('')
        self.assertEqual('Empty section specification is not allowed', str(context.exception))

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
            config.load_context_section('not_allowed')
        self.assertTrue('Root variable names should never include dashes, '
                        'check your vars please: my-var, my-var-with-dashes'
                        in str(context.exception), context.exception)
        c = config.load_context_section('allowed')
        self.assertEqual(c.get('var').get('router').get('your'), 2)

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
                    'section1-key7': "{{ env='CUSTOM_ENV'}} = {{ env='CUSTOM_ENV' }}",
                    'section1-key8': "{{ env='NULL_VAR' }}-{{ env='CUSTOM_ENV' }}"
                }
            },
            'section2': [
                {},
                'var2',
                'var3',
                '{{ env=\'CUSTOM_ENV\' }}',
                '{{ env=\'CUSTOM_ENV\' }} = {{ env=\'CUSTOM_ENV\' }}',
                '{{ env=\'NULL_VAR\' }}-{{ env=\'CUSTOM_ENV\' }}'
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
                    'section1-key7': 'My value = My value',
                    'section1-key8': "-My value"
                }
            },
            'section2': [
                {},
                'var2',
                'var3',
                'My value',
                'My value = My value',
                '-My value'
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

    def test_check_empty_var(self):
        settings.CONFIG_FILE = 'tests/fixtures/config.yaml'
        settings.GET_ENVIRON_STRICT = True
        with self.assertRaises(RuntimeError) as context:
            config.load_context_section('deployment')
        settings.GET_ENVIRON_STRICT = False
        self.assertTrue('Environment variable "EMPTY_ENV" is not set'
                        in str(context.exception))


class TestPriorityEvaluation(unittest.TestCase):
    def test_first_none_argument(self):
        self.assertIsNone(PriorityEvaluator._first())
        self.assertIsNone(PriorityEvaluator._first(None))
        self.assertIsNone(PriorityEvaluator._first(None, False, 0, "", {}, []))

    def test_first_priority(self):
        self.assertEqual(PriorityEvaluator._first(VALUE_CLI, VALUE_ENV), VALUE_CLI)
        self.assertEqual(PriorityEvaluator._first("", VALUE_ENV), VALUE_ENV)

    def test_k8s_namespace_default(self):
        context = {KEY_K8S_NAMESPACE: VALUE_CONTEXT}
        env = {KEY_K8S_NAMESPACE_ENV: VALUE_ENV}
        evaluator = PriorityEvaluator({}, context, env)

        self.assertEqual(evaluator.k8s_namespace_default(), VALUE_CONTEXT)
        self.assertEqual(evaluator.k8s_namespace_default(KUBECONFIG_NAMESPACE), VALUE_CONTEXT)

        context.pop(KEY_K8S_NAMESPACE)
        self.assertEqual(evaluator.k8s_namespace_default(), VALUE_ENV)
        self.assertEqual(evaluator.k8s_namespace_default(KUBECONFIG_NAMESPACE), KUBECONFIG_NAMESPACE)

    def test_k8s_client_configuration_missing_uri(self):
        evaluator = PriorityEvaluator({KEY_K8S_CA_BASE64: VALUE_CLI, KEY_K8S_TOKEN: VALUE_CLI}, {}, {})

        with self.assertRaises(RuntimeError):
            evaluator.k8s_client_configuration()

    def test_k8s_client_configuration_missing_token(self):
        evaluator = PriorityEvaluator({
            KEY_K8S_MASTER_URI: VALUE_CLI,
            KEY_K8S_CA_BASE64: VALUE_CLI,
        }, {}, {})

        with self.assertRaises(RuntimeError):
            evaluator.k8s_client_configuration()

    def test_k8s_client_configuration_success(self):
        evaluator = PriorityEvaluator({
            KEY_K8S_MASTER_URI: VALUE_CLI,
            KEY_K8S_CA_BASE64: VALUE_CA,
            KEY_K8S_TOKEN: VALUE_TOKEN,
        }, {}, {})
        configuration = evaluator.k8s_client_configuration()
        self.assertEqual(configuration.host, VALUE_CLI)
        self.assertEqual(configuration.api_key, {'authorization': 'Bearer token'})
        self.assertEqual(configuration.host, VALUE_CLI)
        self.assertFalse(configuration.debug)

        with open(configuration.ssl_ca_cert) as f:
            self.assertEqual(f.read(), 'CA\n')

        evaluator = PriorityEvaluator({
            KEY_K8S_MASTER_URI: VALUE_CLI,
            KEY_K8S_CA_BASE64: VALUE_CA,
            KEY_K8S_TOKEN: VALUE_TOKEN,
        }, {KEY_K8S_HANDLE_DEBUG: 'true'}, {})
        configuration = evaluator.k8s_client_configuration()
        self.assertTrue(configuration.debug)

    def test_environment_deprecated(self):
        evaluator = PriorityEvaluator({}, {}, {KEY_K8S_CA_BASE64_URI_ENV_DEPRECATED: VALUE_ENV_DEPRECATED})
        self.assertTrue(evaluator.environment_deprecated())
        evaluator = PriorityEvaluator({}, {}, {KEY_K8S_MASTER_URI_ENV_DEPRECATED: VALUE_ENV_DEPRECATED})
        self.assertTrue(evaluator.environment_deprecated())
        evaluator = PriorityEvaluator({}, {}, {KEY_K8S_CA_BASE64_URI_ENV_DEPRECATED: ''})
        self.assertFalse(evaluator.environment_deprecated())
        evaluator = PriorityEvaluator({}, {}, {KEY_K8S_MASTER_URI_ENV_DEPRECATED: ''})
        self.assertFalse(evaluator.environment_deprecated())
