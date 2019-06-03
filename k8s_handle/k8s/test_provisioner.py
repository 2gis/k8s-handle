import unittest

from k8s_handle import settings
from k8s_handle.exceptions import ProvisioningError
from k8s_handle.templating import get_template_contexts
from .adapters import AdapterBuiltinKind
from .mocks import K8sClientMock
from .mocks import ServiceMetadata
from .mocks import ServicePort
from .mocks import ServiceSpec
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

    def test_missing_annotations_and_labels(self):
        annotations = {
            'annotation1': 'value1',
            'annotation2': 'value2',
            'annotation3': 'value3',
            'kubectl.kubernetes.io/last-applied-configuration': {}
        }

        labels = {
            'label1': 'value1',
            'label2': 'value2',
            'label3': 'value3'
        }

        old_metadata = ServiceMetadata(annotations, labels)
        new_metadata = {
            'annotations': {'annotation1': 'value1', 'annotation2': 'value2'},
            'labels': {'label1': 'value1', 'label2': 'value2'}
        }

        missing_annotations, missing_labels = Provisioner('', False, None)._get_missing_annotations_and_labels(
            old_metadata, new_metadata)

        self.assertEqual(len(missing_annotations), 1)
        self.assertEqual(missing_annotations[0], 'annotation3')
        self.assertEqual(len(missing_labels), 1)
        self.assertEqual(missing_labels[0], 'label3')

    def test_no_missing_annotations_and_labels(self):
        annotations = {'annotation1': 'value1'}

        labels = {'label1': 'value1'}

        old_metadata = ServiceMetadata(annotations, labels)
        new_metadata = {
            'annotations': {'annotation1': 'value1', 'annotation2': 'value2'},
            'labels': {'label1': 'value1', 'label2': 'value2'}
        }

        missing_annotations, missing_labels = Provisioner('', False, None)._get_missing_annotations_and_labels(
            old_metadata, new_metadata)

        self.assertEqual(len(missing_annotations), 0)
        self.assertEqual(len(missing_labels), 0)

    def test_no_annotations_in_template(self):
        annotations = {'annotation1': 'value1', 'annotation2': 'value2'}

        labels = {'label1': 'value1'}

        old_metadata = ServiceMetadata(annotations, labels)
        new_metadata = {
            'labels': {'label1': 'value1', 'label2': 'value2'}
        }

        missing_annotations, missing_labels = Provisioner('', False, None)._get_missing_annotations_and_labels(
            old_metadata, new_metadata)

        self.assertEqual(len(missing_annotations), 2)
        self.assertEqual(len(missing_labels), 0)

    def test_no_annotations_in_service_metadata(self):
        labels = {'label1': 'value1'}

        old_metadata = ServiceMetadata(None, labels)
        new_metadata = {
            'annotations': {'annotation1': 'value1'},
            'labels': {'label1': 'value1', 'label2': 'value2'}
        }

        missing_annotations, missing_labels = Provisioner('', False, None)._get_missing_annotations_and_labels(
            old_metadata, new_metadata)

        self.assertEqual(len(missing_annotations), 0)
        self.assertEqual(len(missing_labels), 0)

    def test_missing_annotation_strict(self):
        missing_annotations = ['a1', 'a2', 'a3']
        settings.GET_ENVIRON_STRICT = True
        with self.assertRaises(RuntimeError) as context:
            Provisioner('', False, None)._notify_about_missing_items_in_template(items=missing_annotations,
                                                                                 missing_type='annotation')
        self.assertTrue('Please pay attention to service annotations!'
                        in str(context.exception))

    def test_missing_labels_strict(self):
        missing_labels = ['a1', 'a2', 'a3']
        settings.GET_ENVIRON_STRICT = True
        with self.assertRaises(RuntimeError) as context:
            Provisioner('', False, None)._notify_about_missing_items_in_template(items=missing_labels,
                                                                                 missing_type='label')
        self.assertTrue('Please pay attention to service labels!'
                        in str(context.exception))

    def test_missing_ports_strict(self):
        missing_ports = [ServicePort(80, 'test1'), ServicePort(90, 'test2'), ServicePort(50, None)]
        settings.GET_ENVIRON_STRICT = True
        with self.assertRaises(RuntimeError) as context:
            Provisioner('', False, None)._notify_about_missing_items_in_template(items=missing_ports,
                                                                                 missing_type='port')
        self.assertTrue('Please pay attention to service ports!'
                        in str(context.exception))

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

    def test_get_apply_ports_case1(self):
        # old_port=55, new_port=55, res: no apply ports
        old_spec = ServiceSpec('case1')
        new_spec = {'ports': [{'port': 55}]}
        apply_ports = Provisioner('deploy', False, None)._get_apply_ports(old_spec, new_spec)
        self.assertEqual(len(apply_ports), 0)

    def test_get_apply_ports_case2(self):
        # old_port=55, new_port=56, res: 1 apply port, 1 deleted
        old_spec = ServiceSpec('case2')
        new_spec = {'ports': [{'port': 56}]}
        apply_ports = Provisioner('deploy', False, None)._get_apply_ports(old_spec, new_spec)
        self.assertEqual(len(apply_ports), 2)
        self.assertDictEqual(apply_ports[0], {'port': 55, '$patch': 'delete'})
        self.assertDictEqual(apply_ports[1], {'port': 56})

    def test_get_apply_ports_case3(self):
        # old_port=55, new_port=56, name=test, res: 1 apply port, 1 deleted
        old_spec = ServiceSpec('case3')
        new_spec = {'ports': [{'port': 56, 'name': 'test'}]}
        apply_ports = Provisioner('deploy', False, None)._get_apply_ports(old_spec, new_spec)
        self.assertEqual(len(apply_ports), 2)
        self.assertDictEqual(apply_ports[0], {'port': 55, '$patch': 'delete'})
        self.assertDictEqual(apply_ports[1], {'port': 56, 'name': 'test'})

    def test_get_apply_ports_case4(self):
        # old_port=55,name=test, new_port=56,name=test, res: 1 apply port, 1 deleted
        old_spec = ServiceSpec('case4')
        new_spec = {'ports': [{'port': 56, 'name': 'foo'}]}
        apply_ports = Provisioner('deploy', False, None)._get_apply_ports(old_spec, new_spec)
        self.assertEqual(len(apply_ports), 2)
        self.assertDictEqual(apply_ports[0], {'port': 55, '$patch': 'delete'})
        self.assertDictEqual(apply_ports[1], {'port': 56, 'name': 'foo'})

    def test_get_apply_ports_case5(self):
        # add targetPort to existent port, res: 1 apply port
        old_spec = ServiceSpec('case5')
        new_spec = {'ports': [{'port': 55, 'name': 'test', 'targetPort': 90}]}
        apply_ports = Provisioner('deploy', False, None)._get_apply_ports(old_spec, new_spec)
        self.assertEqual(len(apply_ports), 1)
        self.assertDictEqual(apply_ports[0], {'port': 55, 'node_port': None,
                                              'protocol': 'TCP', 'name': 'test', 'targetPort': 90})

    def test_get_apply_ports_case6(self):
        # change targetPort, res: 1 apply port
        old_spec = ServiceSpec('case6')
        new_spec = {'ports': [{'port': 55, 'name': 'test', 'targetPort': 99}]}
        apply_ports = Provisioner('deploy', False, None)._get_apply_ports(old_spec, new_spec)
        self.assertEqual(len(apply_ports), 1)
        self.assertDictEqual(apply_ports[0], {'port': 55, 'node_port': None,
                                              'protocol': 'TCP', 'name': 'test', 'targetPort': 99})

    def test_get_apply_ports_case7(self):
        # change protocol, res: 1 apply port
        old_spec = ServiceSpec('case7')
        new_spec = {'ports': [{'port': 55, 'name': 'test', 'protocol': 'UDP'}]}
        apply_ports = Provisioner('deploy', False, None)._get_apply_ports(old_spec, new_spec)
        self.assertEqual(len(apply_ports), 1)
        self.assertDictEqual(apply_ports[0], {'port': 55, 'node_port': None,
                                              'protocol': 'UDP', 'name': 'test', 'target_port': 55})

    def test_get_apply_ports_case8(self):
        # add new ports, res: 1 delete, 2 apply
        old_spec = ServiceSpec('case8')
        new_spec = {'ports': [{'port': 90, 'name': 'test1'},
                              {'port': 99, 'name': 'test2'}]}
        apply_ports = Provisioner('deploy', False, None)._get_apply_ports(old_spec, new_spec)
        self.assertEqual(len(apply_ports), 3)
        self.assertDictEqual(apply_ports[0], {'port': 55, '$patch': 'delete'})
        self.assertDictEqual(apply_ports[1], {'port': 90, 'name': 'test1'})
        self.assertDictEqual(apply_ports[2], {'port': 99, 'name': 'test2'})

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
