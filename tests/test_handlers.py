import os
import unittest
from unittest.mock import patch

from k8s_handle import settings
from k8s_handle import handler_deploy
from kubernetes import client


class TestDeployHandler(unittest.TestCase):

    def setUp(self):
        settings.CONFIG_FILE = 'tests/fixtures/config_with_env_vars.yaml'
        settings.TEMPLATES_DIR = 'templates/tests'
        os.environ['K8S_CONFIG_DIR'] = '/tmp/kube/'
        os.environ['SECTION1'] = 'not found'
        os.environ['SECTION'] = 'section-1'

    @patch('k8s_handle.templating.Renderer._generate_file')
    @patch('kubernetes.client.api.version_api.VersionApi.get_code_with_http_info')
    @patch('k8s_handle.k8s.provisioner.Provisioner.run')
    def test_api_exception_handling(
        self,
        mocked_provisioner_run,
        mocked_client_version_api_get_code,
        mocked_generate_file
    ):
        mocked_client_version_api_get_code.side_effect = client.exceptions.ApiException(
            'Max retries exceeded with url: /version/'
        )

        configs = {
            'section': os.environ['SECTION'],
            'config': settings.CONFIG_FILE,
        }
        # client.exceptions.ApiException should be handled
        handler_deploy(configs)
