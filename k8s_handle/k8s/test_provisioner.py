import unittest

from k8s_handle import settings
from k8s_handle.exceptions import ProvisioningError
from k8s_handle.templating import get_template_contexts
from .adapters import AdapterBuiltinKind
from .mocks import K8sClientMock
from .provisioner import Provisioner


class TestProvisioner(unittest.TestCase):
    def setUp(self):
        settings.GET_ENVIRON_STRICT = False

    def test_deployment_wait_complete_fail(self):
        client = AdapterBuiltinKind(
            api=K8sClientMock('test1'),
            spec={'kind': 'Deployment', 'metadata': {'name': 'test1'}, 'spec': {'replicas': 1}})
        with self.assertRaises(RuntimeError) as context:
            Provisioner('deploy', False, None)._wait_deployment_complete(client, tries=1, timeout=0)
        self.assertTrue('Deployment not completed for 1 tries' in str(context.exception), context.exception)

    def test_deployment_wait_complete(self):
        client = AdapterBuiltinKind(
            api=K8sClientMock('test2'),
            spec={'kind': 'Deployment', 'metadata': {'name': 'test1'}, 'spec': {'replicas': 1}})
        Provisioner('deploy', False, None)._wait_deployment_complete(client, tries=1, timeout=0)

    def test_statefulset_wait_complete_fail(self):
        client = AdapterBuiltinKind(api=K8sClientMock('test1'),
                                    spec={'kind': 'StatefulSet', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        with self.assertRaises(RuntimeError) as context:
            Provisioner('deploy', False, None)._wait_statefulset_complete(client, tries=1, timeout=0)
        self.assertTrue('StatefulSet not completed for 1 tries' in str(context.exception), context.exception)

    def test_statefulset_wait_complete(self):
        client = AdapterBuiltinKind(api=K8sClientMock('test2'),
                                    spec={'kind': 'StatefulSet', 'metadata': {'name': ''}, 'spec': {'replicas': 3}})
        Provisioner('deploy', False, None)._wait_statefulset_complete(client, tries=1, timeout=0)

    def test_daemonset_wait_complete_fail(self):
        client = AdapterBuiltinKind(api=K8sClientMock('test1'),
                                    spec={'kind': 'DaemonSet', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        with self.assertRaises(RuntimeError) as context:
            Provisioner('deploy', False, None)._wait_daemonset_complete(client, tries=1, timeout=0)
        self.assertTrue('DaemonSet not completed for 1 tries' in str(context.exception), context.exception)

    def test_daemonset_wait_complete(self):
        client = AdapterBuiltinKind(api=K8sClientMock('test2'),
                                    spec={'kind': 'DaemonSet', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        Provisioner('deploy', False, None)._wait_daemonset_complete(client, tries=1, timeout=0)

    def test_job_wait_complete_fail(self):
        client = AdapterBuiltinKind(api=K8sClientMock('test1'),
                                    spec={'kind': 'Job', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        with self.assertRaises(RuntimeError) as context:
            Provisioner('deploy', False, None)._wait_job_complete(client, tries=1, timeout=0)

        self.assertTrue('Job running failed' in str(context.exception))

    def test_job_wait_complete_conditions_fail(self):
        client = AdapterBuiltinKind(api=K8sClientMock('test2'),
                                    spec={'kind': 'Job', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        with self.assertRaises(RuntimeError) as context:
            Provisioner('deploy', False, None)._wait_job_complete(client, tries=1, timeout=0)
        self.assertTrue('Job not completed for 1 tries' in str(context.exception), context.exception)

    def test_job_wait_complete(self):
        client = AdapterBuiltinKind(api=K8sClientMock('test3'),
                                    spec={'kind': 'Job', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        Provisioner('deploy', False, None)._wait_job_complete(client, tries=1, timeout=0)

    def test_ns_from_template(self):
        client = AdapterBuiltinKind(api=K8sClientMock('test'),
                                    spec={'kind': 'Job', 'metadata': {'name': '', 'namespace': 'test'},
                                          'spec': {'replicas': 1}})
        self.assertEqual(client.namespace, 'test')

    def test_ns_from_config(self):
        settings.K8S_NAMESPACE = 'namespace'
        client = AdapterBuiltinKind(api=K8sClientMock('test'),
                                    spec={'kind': 'Job', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        self.assertEqual(client.namespace, 'namespace')

    def test_deployment_destruction_wait_fail(self):
        client = AdapterBuiltinKind(
            api=K8sClientMock('test1'),
            spec={'kind': 'Deployment', 'metadata': {'name': 'test1'}, 'spec': {'replicas': 1}})
        with self.assertRaises(RuntimeError) as context:
            Provisioner('destroy', False, None)._wait_destruction_complete(client, 'Deployment', tries=1, timeout=0)
        self.assertTrue('Deployment destruction not completed for 1 tries' in str(context.exception), context.exception)

    def test_deployment_destruction_wait_success(self):
        client = AdapterBuiltinKind(
            api=K8sClientMock('404'),
            spec={'kind': 'Deployment', 'metadata': {'name': 'test1'}, 'spec': {'replicas': 1}})
        Provisioner('destroy', False, None)._wait_destruction_complete(client, 'Deployment', tries=1, timeout=0)

    def test_job_destruction_wait_fail(self):
        client = AdapterBuiltinKind(
            api=K8sClientMock('test1'),
            spec={'kind': 'Job', 'metadata': {'name': 'test1'}, 'spec': {'replicas': 1}})
        with self.assertRaises(RuntimeError) as context:
            Provisioner('deploy', True, None)._wait_destruction_complete(client, 'Job', tries=1, timeout=0)
        self.assertTrue('Job destruction not completed for 1 tries' in str(context.exception), context.exception)

    def test_job_destruction_wait_success(self):
        client = AdapterBuiltinKind(
            api=K8sClientMock('404'),
            spec={'kind': 'Job', 'metadata': {'name': 'test1'}, 'spec': {'replicas': 1}})
        Provisioner('destroy', False, None)._wait_destruction_complete(client, 'Job', tries=1, timeout=0)

    def test_deploy_replace(self):
        settings.CHECK_STATUS_TIMEOUT = 0
        Provisioner('deploy', False, None).run("k8s_handle/k8s/fixtures/deployment.yaml")

    def test_deploy_create(self):
        Provisioner('deploy', False, None).run("k8s_handle/k8s/fixtures/deployment_404.yaml")

    def test_deploy_unknown_api(self):
        with self.assertRaises(RuntimeError) as context:
            Provisioner('deploy', False, None).run("k8s_handle/k8s/fixtures/deployment_no_api.yaml")
        self.assertTrue('Unknown apiVersion "test" in template "k8s_handle/k8s/fixtures/deployment_no_api.yaml"'
                        in str(context.exception), context.exception)

    def test_service_replace(self):
        Provisioner('deploy', False, None).run("k8s_handle/k8s/fixtures/service.yaml")

    def test_service_replace_no_ports(self):
        Provisioner('deploy', False, None).run("k8s_handle/k8s/fixtures/service_no_ports.yaml")

    def test_destroy_unknown_api(self):
        with self.assertRaises(RuntimeError) as context:
            Provisioner('destroy', False, None).run("k8s_handle/k8s/fixtures/deployment_no_api.yaml")
        self.assertTrue('Unknown apiVersion "test" in template "k8s_handle/k8s/fixtures/deployment_no_api.yaml"'
                        in str(context.exception), context.exception)

    def test_destroy_not_found(self):
        Provisioner('destroy', False, None).run("k8s_handle/k8s/fixtures/deployment_404.yaml")

    def test_destroy_fail(self):
        with self.assertRaises(RuntimeError) as context:
            Provisioner('destroy', False, None).run("k8s_handle/k8s/fixtures/service.yaml")
        self.assertTrue('' in str(context.exception), context.exception)

    def test_destroy_success(self):
        Provisioner('destroy', False, None).run("k8s_handle/k8s/fixtures/deployment.yaml")

    def test_pvc_replace_equals(self):
        Provisioner('deploy', False, None).run("k8s_handle/k8s/fixtures/pvc.yaml")

    def test_pvc_replace_not_equals(self):
        with self.assertRaises(ProvisioningError) as context:
            Provisioner('deploy', False, None).run("k8s_handle/k8s/fixtures/pvc2.yaml")
        self.assertTrue('Replace persistent volume claim fail' in str(context.exception), context.exception)

    # https://kubernetes.io/docs/concepts/storage/persistent-volumes/#volume-mode
    def test_pvc_replace_new_attribute(self):
        with self.assertRaises(ProvisioningError) as context:
            Provisioner('deploy', False, None).run("k8s_handle/k8s/fixtures/pvc3.yaml")
        self.assertTrue('Replace persistent volume claim fail'
                        in str(context.exception))

    def test_get_template_contexts(self):
        with self.assertRaises(StopIteration):
            next(get_template_contexts('k8s_handle/k8s/fixtures/empty.yaml'))

        with self.assertRaises(RuntimeError) as context:
            next(get_template_contexts('k8s_handle/k8s/fixtures/nokind.yaml'))
        self.assertTrue(
            'Field "kind" not found (or empty) in file "k8s_handle/k8s/fixtures/nokind.yaml"' in str(context.exception),
            context.exception)

        with self.assertRaises(RuntimeError) as context:
            next(get_template_contexts('k8s_handle/k8s/fixtures/nometadata.yaml'))
        self.assertTrue(
            'Field "metadata" not found (or empty) in file "k8s_handle/k8s/fixtures/nometadata.yaml"'
            in str(context.exception),
            context.exception)

        with self.assertRaises(RuntimeError) as context:
            next(get_template_contexts('k8s_handle/k8s/fixtures/nometadataname.yaml'))
        self.assertTrue(
            'Field "metadata->name" not found (or empty) in file "k8s_handle/k8s/fixtures/nometadataname.yaml"'
            in str(context.exception), context.exception)

        context = next(get_template_contexts('k8s_handle/k8s/fixtures/valid.yaml'))
        self.assertEqual(context.get('kind'), 'Service')
        self.assertEqual(context.get('apiVersion'), 'v1')
        self.assertEqual(context.get('metadata').get('name'), 'my-service')
        self.assertEqual(context.get('spec').get('selector').get('app'), 'my-app')

        context = next(get_template_contexts('k8s_handle/k8s/fixtures/deployment_wo_replicas.yaml'))
        self.assertEqual(context.get('spec').get('replicas'), 1)


class TestKubeObject(unittest.TestCase):
    def test_replicas_equal(self):
        replicas = (1, 1, 1)
        self.assertTrue(Provisioner._replicas_count_are_equal(replicas))

    def test_replicas_not_equal(self):
        replicas = (1, 1, 0)
        self.assertFalse(Provisioner._replicas_count_are_equal(replicas))
