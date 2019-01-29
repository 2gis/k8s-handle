import json
import logging
import re
from time import sleep

from kubernetes import client
from kubernetes.client.models.v1_label_selector import V1LabelSelector
from kubernetes.client.models.v1_label_selector_requirement import V1LabelSelectorRequirement
from kubernetes.client.models.v1_resource_requirements import V1ResourceRequirements
from kubernetes.client.rest import ApiException

from k8s_handle import settings
from k8s_handle.templating import get_template_contexts
from .mocks import K8sClientMock

log = logging.getLogger(__name__)


class ProvisioningError(Exception):
    pass


def _split_str_by_capital_letters(item):
    # upper the first letter
    item = item[0].upper() + item[1:]
    # transform 'Service' to 'service', 'CronJob' to 'cron_job', 'TargetPort' to 'target_port', etc.
    return '_'.join(re.findall(r'[A-Z][^A-Z]*', item)).lower()


class Provisioner:
    def __init__(self, command, sync_mode, show_logs):
        self.command = command
        self.sync_mode = False if show_logs else sync_mode
        self.show_logs = show_logs

    @staticmethod
    def _replicas_count_are_greater_or_equal(replicas):
        replicas = [0 if r is None else r for r in replicas]  # replace all None to 0
        return all(r >= replicas[0] for r in replicas)

    @staticmethod
    def _ports_are_equal(old_port, new_port):
        for new_key in new_port.keys():
            old_key = _split_str_by_capital_letters(new_key)
            if getattr(old_port, old_key, None) != new_port.get(new_key, None):
                return False
        return True

    @staticmethod
    def _get_missing_items_in_metadata_field(items, metadata, field):
        if field not in metadata:
            result = [item for item in items if 'kubernetes.io' not in item]
        else:
            result = [item for item in items if
                      item not in metadata[field] and 'kubernetes.io' not in item]

        return result

    @staticmethod
    def _port_obj_to_str(port):
        if hasattr(port, 'name') and hasattr(port, 'port'):
            return '{} ({})'.format(port.name, port.port)
        return '{}'.format(port.port)

    def _notify_about_missing_items_in_template(self, items, missing_type):
        skull = r"""
       ___
    .-'   `-.
   /  \   /  \\     Please pay attention to service {type}s!
  .   o\ /o   .    The next {type}(s) missing in template:
  |___  ^  ___|    "{list}"
      |___|        They won\'t be deleted after service apply.
      |||||
                    """

        if len(items) != 0:
            if missing_type in ['port', ]:
                items = [self._port_obj_to_str(item) for item in items]

            log_text = skull.format(type=missing_type, list=', '.join(items))
            if settings.GET_ENVIRON_STRICT:
                raise RuntimeError(log_text)
            log.warning(log_text)

    @staticmethod
    def _is_job_complete(status):
        if status.failed is not None:
            raise RuntimeError('Job running failed')

        if status.conditions is not None:
            for condition in status.conditions:
                if condition.type == 'Complete':
                    return True
        else:
            return False

    def _get_missing_annotations_and_labels(self, old_metadata, new_metadata):
        missing_annotations = []
        missing_labels = []

        if hasattr(old_metadata, 'annotations') and old_metadata.annotations is not None:
            missing_annotations = self._get_missing_items_in_metadata_field(
                old_metadata.annotations, new_metadata, 'annotations')
        if hasattr(old_metadata, 'labels') and old_metadata.labels is not None:
            missing_labels = self._get_missing_items_in_metadata_field(
                old_metadata.labels, new_metadata, 'labels')

        return missing_annotations, missing_labels

    def _get_apply_ports(self, old_spec, new_spec):
        ports = []

        if hasattr(old_spec, 'ports') and old_spec.ports is not None:
            if 'ports' not in new_spec:
                return []

            new_ports = new_spec['ports']
            for old_port in old_spec.ports:
                res = [item for item in new_ports if item['port'] == old_port.port]

                if len(res) == 0:
                    log.warning('Port {} will be deleted'.format(old_port.port))
                    ports.append({'$patch': 'delete', 'port': old_port.port})

                if len(res) == 1:
                    new_port = self._add_defaults_to_port(res[0])
                    if not self._ports_are_equal(old_port, new_port):
                        ports.append(new_port)

            for new_port in new_ports:
                res = [item for item in old_spec.ports if item.port == new_port['port']]

                if len(res) == 0:
                    ports.append(new_port)

        return ports

    @staticmethod
    def _add_defaults_to_port(port):
        if 'name' not in port:
            port['name'] = None
        if 'nodePort' not in port:
            port['node_port'] = None
        if 'protocol' not in port:
            port['protocol'] = 'TCP'
        if 'targetPort' not in port:
            port['target_port'] = port['port']

        return port

    def run(self, file_path):
        if self.command == 'deploy':
            self._deploy_all(file_path)
        if self.command == 'destroy':
            self._destroy_all(file_path)

    def _is_pvc_specs_equals(self, old_obj, new_dict):
        for new_key in new_dict.keys():
            old_key = _split_str_by_capital_letters(new_key)

            # if template has some new attributes
            if not hasattr(old_obj, old_key):
                return False
            old_value = getattr(old_obj, old_key)

            if isinstance(old_value, list) and \
                    isinstance(old_value[0], V1LabelSelectorRequirement):
                if len(old_value) != len(new_dict[new_key]):
                    return False
                for i in range(0, len(old_value)):
                    if not self._is_pvc_specs_equals(old_value[i], new_dict[new_key][i]):
                        return False

            elif isinstance(old_value, (V1ResourceRequirements, V1LabelSelector)):
                if not self._is_pvc_specs_equals(old_value, new_dict[new_key]):
                    return False

            elif old_value != new_dict[new_key]:
                log.error('{} != {}'.format(old_value, new_dict[new_key]))
                return False

        return True

    def _deploy_all(self, file_path):
        for template_body in get_template_contexts(file_path):
            self._deploy(template_body, file_path)

    def _deploy(self, template_body, file_path):
        kube_client = Adapter(template_body)
        log.info('Using namespace "{}"'.format(kube_client.namespace))

        if kube_client.api is None:
            raise RuntimeError('Unknown apiVersion "{}" in template "{}"'.format(template_body['apiVersion'],
                                                                                 file_path))

        if kube_client.get() is None:
            log.info('{} "{}" does not exist, create it'.format(template_body['kind'], kube_client.name))
            kube_client.create()
        else:
            log.info('{} "{}" already exists, replace it'.format(template_body['kind'], kube_client.name))

            apply_ports = None
            if template_body['kind'] == 'Service':
                resource = kube_client.get()

                missing_annotations, missing_labels = \
                    self._get_missing_annotations_and_labels(resource.metadata, template_body['metadata'])
                apply_ports = self._get_apply_ports(resource.spec, template_body['spec'])

                self._notify_about_missing_items_in_template(missing_annotations, 'annotation')
                self._notify_about_missing_items_in_template(missing_labels, 'label')

                if len(apply_ports) != 0:
                    log.info('Next ports will be apply: {}'.format(apply_ports))

            if template_body['kind'] == 'PersistentVolumeClaim':
                resource = kube_client.get()
                if self._is_pvc_specs_equals(resource.spec, template_body['spec']):
                    log.info('PersistentVolumeClaim is not changed')
                    return

            if template_body['kind'] == 'PersistentVolume':
                resource = kube_client.get()
                if resource.status.phase in ['Bound', 'Released']:
                    log.warning('PersistentVolume has "{}" status, skip replacing'.format(resource.status.phase))
                    return

            kube_client.replace(apply_ports)

        if template_body['kind'] == 'Deployment' and self.sync_mode:
            self._wait_deployment_complete(kube_client,
                                           tries=settings.CHECK_STATUS_TRIES,
                                           timeout=settings.CHECK_STATUS_TIMEOUT)

        if template_body['kind'] == 'StatefulSet' and self.sync_mode:
            self._wait_statefulset_complete(kube_client,
                                            tries=settings.CHECK_STATUS_TRIES,
                                            timeout=settings.CHECK_STATUS_TIMEOUT)

        if template_body['kind'] == 'DaemonSet' and self.sync_mode:
            self._wait_daemonset_complete(kube_client,
                                          tries=settings.CHECK_STATUS_TRIES,
                                          timeout=settings.CHECK_STATUS_TIMEOUT)

        if template_body['kind'] == 'Job' and self.sync_mode:
            return self._wait_job_complete(kube_client,
                                           tries=settings.CHECK_STATUS_TRIES,
                                           timeout=settings.CHECK_STATUS_TIMEOUT)

        if template_body['kind'] == 'Job' and self.show_logs:
            log.info("Got into section")
            pod_name, pod_containers = self._get_pod_name_and_containers_by_selector(
                kube_client,
                template_body['metadata']['name'],
                tries=settings.CHECK_STATUS_TRIES,
                timeout=settings.CHECK_STATUS_TIMEOUT)

            log.info("Got pod name and pod containers {} {}".format(pod_name, pod_containers))

            if not pod_name:
                log.warning('Pod not found for showing logs')
                return

            is_successful = self._wait_pod_running(
                kube_client,
                pod_name,
                tries=settings.CHECK_STATUS_TRIES,
                timeout=settings.CHECK_STATUS_TIMEOUT)

            for pod_container in pod_containers:
                log.info('\n{}'.format(kube_client.read_pod_logs(pod_name, pod_container)))

            if not is_successful:
                raise RuntimeError('Job running failed')

    def _destroy_all(self, file_path):
        for template_body in get_template_contexts(file_path):
            self._destroy(template_body, file_path)

    def _destroy(self, template_body, file_path):
        kube_client = Adapter(template_body)
        log.info('Using namespace "{}"'.format(kube_client.namespace))
        log.info('Trying to delete {} "{}"'.format(template_body['kind'], kube_client.name))
        if kube_client.api is None:
            raise RuntimeError('Unknown apiVersion "{}" in template "{}"'.format(template_body['apiVersion'],
                                                                                 file_path))

        response = kube_client.delete()
        if response is None:
            return

        if response.message is not None:
            raise RuntimeError('{} "{}" deletion failed: {}'.format(
                template_body['kind'], kube_client.name, response.message))
        else:
            if self.sync_mode:
                self._wait_destruction_complete(kube_client, template_body['kind'],
                                                tries=settings.CHECK_STATUS_TRIES,
                                                timeout=settings.CHECK_STATUS_TIMEOUT)

            log.info('{} "{}" deleted'.format(template_body['kind'], kube_client.name))

    @staticmethod
    def _get_pod_name_and_containers_by_selector(kube_client, selector, tries, timeout):
        for i in range(0, tries):
            pod = kube_client.get_pods_by_selector(selector)

            if len(pod.items) == 1:
                log.info('Found pod "{}"'.format(pod.items[0].metadata.name))
                containers = [container.name for container in pod.items[0].spec.containers]
                return pod.items[0].metadata.name, containers
            else:
                if len(pod.items) == 0:
                    log.warning('No pods found by job-name={}, next attempt in {} sec.'.format(selector, timeout))
                else:
                    names = [pod.metadata.name for pod in pod.items]
                    log.warning('More than one pod found by job-name={}: {}, '
                                'next attempt in {} sec.'.format(selector, names, timeout))
            sleep(timeout)

        log.error('Problems with getting pod by selector job-name={} for {} tries'.format(selector, tries))
        return '', []

    def _wait_deployment_complete(self, kube_client, tries, timeout):
        for i in range(0, tries):
            sleep(timeout)
            status = kube_client.get().status

            replicas = [kube_client.replicas, status.replicas, status.available_replicas,
                        status.ready_replicas, status.updated_replicas]

            log.info('desiredReplicas = {}, updatedReplicas = {}, availableReplicas = {}'.
                     format(replicas[0], replicas[4], replicas[2]))
            if self._replicas_count_are_greater_or_equal(replicas) and status.unavailable_replicas is None:
                log.info('Deployment completed on {} attempt'.format(i + 1))
                return
            else:
                log.info('Deployment not completed on {} attempt, next attempt in {} sec.'.format(i + 1, timeout))

        raise RuntimeError('Deployment not completed for {} tries'.format(tries))

    def _wait_statefulset_complete(self, kube_client, tries, timeout):
        for i in range(0, tries):
            sleep(timeout)
            status = kube_client.get().status

            current_revision = status.current_revision
            update_revision = status.update_revision
            replicas = [kube_client.replicas, status.current_replicas, status.ready_replicas]

            log.info('Current revision {}, should be {}'.format(current_revision, update_revision))
            if current_revision == update_revision:
                log.info('desiredReplicas = {}, updatedReplicas = {}, availableReplicas = {}'.
                         format(replicas[0], replicas[1], replicas[2]))
                if self._replicas_count_are_greater_or_equal(replicas):
                    log.info('StatefulSet completed on {} attempt'.format(i))
                    return
            else:
                log.info('StatefulSet not completed on {} attempt, next attempt in {} sec.'.format(i, timeout))

        raise RuntimeError('StatefulSet not completed for {} tries'.format(tries))

    def _wait_daemonset_complete(self, kube_client, tries, timeout):
        for i in range(0, tries):
            sleep(timeout)
            status = kube_client.get().status

            replicas = [status.desired_number_scheduled, status.number_available,
                        status.number_ready, status.updated_number_scheduled]
            log.info('desiredNodes = {}, availableNodes = {}, readyNodes = {}, updatedNodes = {}'.
                     format(replicas[0], replicas[1], replicas[2], replicas[3]))
            if self._replicas_count_are_greater_or_equal(replicas) and status.number_unavailable is None:
                log.info('DaemonSet completed on {} attempt'.format(i))
                return
            else:
                log.info('DaemonSet not completed on {} attempt, next attempt in {} sec.'.format(i, timeout))

        raise RuntimeError('DaemonSet not completed for {} tries'.format(tries))

    def _wait_job_complete(self, kube_client, tries, timeout):
        for i in range(0, tries):
            sleep(timeout)
            status = kube_client.get().status
            if self._is_job_complete(status):
                log.info('Job completed on {} attempt'.format(i))
                return
            else:
                log.info('Job not completed on {} attempt, next attempt in {} sec.'.format(i, timeout))

        raise RuntimeError('Job not completed for {} tries'.format(tries))

    @staticmethod
    def _wait_pod_running(kube_client, pod_name, tries, timeout):
        for i in range(0, tries):
            status = kube_client.read_pod_status(pod_name)

            log.info('Pod "{}" status: {}'.format(pod_name, status.status.phase))
            if status.status.phase == 'Succeeded':
                return True
            if status.status.phase in ['Failed', 'Unknown']:
                return False
            sleep(timeout)

        raise RuntimeError('Pod "{}" not completed for {} tries'.format(pod_name, tries))

    @staticmethod
    def _wait_destruction_complete(kube_client, kind, tries, timeout):
        for i in range(0, tries):
            sleep(timeout)
            if kube_client.get() is None:
                log.info('{} destruction completed on {} attempt'.format(kind, i + 1))
                return
            else:
                log.info('{} destruction not completed on {} attempt, '
                         'next attempt in {} sec.'.format(kind, i + 1, timeout))

        raise RuntimeError('{} destruction not completed for {} tries'.format(kind, tries))


class Adapter:
    def __init__(self, spec, api=None):
        self.kind = self._get_app_kind(spec['kind'])
        self.name = spec['metadata']['name']
        self.body = spec
        self.replicas = None if 'spec' not in spec or 'replicas' not in spec['spec'] else spec['spec']['replicas']
        self.namespace = spec['metadata']['namespace'] if 'namespace' in spec['metadata'] else settings.K8S_NAMESPACE

        if api is not None:
            self.api = api
        else:
            self.api = self._detect_api_object(spec['apiVersion'])

    def _detect_api_object(self, api_version):
        # Due to https://github.com/kubernetes-client/python/issues/387
        if api_version == 'apps/v1beta1':
            return client.AppsV1beta1Api()
        if api_version == 'v1':
            return client.CoreV1Api()
        if api_version == 'extensions/v1beta1':
            return client.ExtensionsV1beta1Api()
        if api_version == 'batch/v1':
            return client.BatchV1Api()
        if api_version == 'batch/v2alpha1':
            return client.BatchV2alpha1Api()
        if api_version == 'batch/v1beta1':
            return client.BatchV1beta1Api()
        if api_version == 'policy/v1beta1':
            return client.PolicyV1beta1Api()
        if api_version == 'storage.k8s.io/v1':
            return client.StorageV1Api()
        if api_version == 'apps/v1':
            return client.AppsV1Api()
        if api_version == 'autoscaling/v1':
            return client.AutoscalingV1Api()
        if api_version == 'rbac.authorization.k8s.io/v1':
            return client.RbacAuthorizationV1Api()
        if api_version == 'scheduling.k8s.io/v1alpha1':
            return client.SchedulingV1alpha1Api()
        if api_version == 'scheduling.k8s.io/v1beta1':
            return client.SchedulingV1beta1Api()
        if api_version == 'test/test':
            return K8sClientMock(self.name)

    @staticmethod
    def _get_app_kind(kind):
        if kind not in ['ConfigMap', 'CronJob', 'DaemonSet', 'Deployment', 'Endpoints',
                        'Ingress', 'Job', 'Namespace', 'PodDisruptionBudget', 'ResourceQuota',
                        'Secret', 'Service', 'ServiceAccount', 'StatefulSet', 'StorageClass',
                        'PersistentVolume', 'PersistentVolumeClaim', 'HorizontalPodAutoscaler',
                        'Role', 'RoleBinding', 'ClusterRole', 'ClusterRoleBinding',
                        'PriorityClass', 'PodSecurityPolicy', 'LimitRange']:
            raise RuntimeError('Unknown kind "{}" in generated file'.format(kind))

        return _split_str_by_capital_letters(kind)

    def get(self):
        try:
            if hasattr(self.api, "read_namespaced_{}".format(self.kind)):
                response = getattr(self.api, 'read_namespaced_{}'.format(self.kind))(
                    self.name, namespace=self.namespace)
            else:
                response = getattr(self.api, 'read_{}'.format(self.kind))(self.name)
        except ApiException as e:
            if e.reason == 'Not Found':
                return None
            log.error('Exception when calling "read_namespaced_{}": {}'.format(self.kind, self._add_indent(e.body)))
            raise ProvisioningError(e)

        return response

    def get_pods_by_selector(self, label_selector):
        try:
            if not isinstance(self.api, K8sClientMock):
                self.api = client.CoreV1Api()

            return self.api.list_namespaced_pod(
                namespace=self.namespace, label_selector='job-name={}'.format(label_selector))

        except ApiException as e:
            log.error('Exception when calling CoreV1Api->list_namespaced_pod: {}', e)
            raise e

    def read_pod_status(self, name):
        try:
            if not isinstance(self.api, K8sClientMock):
                self.api = client.CoreV1Api()

            return self.api.read_namespaced_pod_status(name, namespace=self.namespace)
        except ApiException as e:
            log.error('Exception when calling CoreV1Api->read_namespaced_pod_status: {}', e)
            raise e

    def read_pod_logs(self, name, container):
        log.info('Read logs for pod "{}", container "{}"'.format(name, container))
        try:
            if not isinstance(self.api, K8sClientMock):
                self.api = client.CoreV1Api()
            if settings.COUNT_LOG_LINES:
                return self.api.read_namespaced_pod_log(name, namespace=self.namespace, timestamps=True,
                                                        tail_lines=settings.COUNT_LOG_LINES, container=container)
            return self.api.read_namespaced_pod_log(name, namespace=self.namespace, timestamps=True,
                                                    container=container)
        except ApiException as e:
            log.error('Exception when calling CoreV1Api->read_namespaced_pod_log: {}', e)
            raise e

    def create(self):
        try:
            if hasattr(self.api, "create_namespaced_{}".format(self.kind)):
                return getattr(self.api, 'create_namespaced_{}'.format(self.kind))(
                    body=self.body, namespace=self.namespace)

            return getattr(self.api, 'create_{}'.format(self.kind))(body=self.body)
        except ApiException as e:
            log.error('Exception when calling "create_namespaced_{}": {}'.format(self.kind, self._add_indent(e.body)))
            raise ProvisioningError(e)
        except ValueError as e:
            log.error(e)
            # WORKAROUND https://github.com/kubernetes-client/python/issues/466
            if self.kind != 'pod_disruption_budget':
                raise e

    def replace(self, ports=None):
        try:
            if self.kind in ['service', 'service_account', ]:
                if ports is not None:
                    self.body['spec']['ports'] = ports
                return getattr(self.api, 'patch_namespaced_{}'.format(self.kind))(
                    name=self.name, body=self.body, namespace=self.namespace
                )

            if hasattr(self.api, "replace_namespaced_{}".format(self.kind)):
                return getattr(self.api, 'replace_namespaced_{}'.format(self.kind))(
                    name=self.name, body=self.body, namespace=self.namespace)

            return getattr(self.api, 'replace_{}'.format(self.kind))(
                name=self.name, body=self.body)
        except ApiException as e:
            log.error('Exception when calling "replace_namespaced_{}": {}'.format(self.kind, self._add_indent(e.body)))
            raise ProvisioningError(e)

    def delete(self):
        try:
            if hasattr(self.api, "delete_namespaced_{}".format(self.kind)):
                return getattr(self.api, 'delete_namespaced_{}'.format(self.kind))(
                    name=self.name, body=client.V1DeleteOptions(propagation_policy='Foreground'),
                    namespace=self.namespace)

            return getattr(self.api, 'delete_{}'.format(self.kind))(
                name=self.name, body=client.V1DeleteOptions(propagation_policy='Foreground'))
        except ApiException as e:
            if e.reason == 'Not Found':
                return None
            log.error('Exception when calling "delete_namespaced_{}": {}'.format(self.kind, self._add_indent(e.body)))
            raise ProvisioningError(e)

    @staticmethod
    def _add_indent(json_str):
        try:
            return json.dumps(json.loads(json_str), indent=4)
        except:  # NOQA
            return json_str
