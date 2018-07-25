import re
import logging
import yaml
import json

import settings

from .mocks import K8sClientMock

from kubernetes import client

from kubernetes.client.rest import ApiException

from kubernetes.client.models.v1_resource_requirements import V1ResourceRequirements
from kubernetes.client.models.v1_label_selector import V1LabelSelector
from kubernetes.client.models.v1_label_selector_requirement import V1LabelSelectorRequirement

from time import sleep

log = logging.getLogger(__name__)


class ProvisioningError(Exception):
    pass


def _split_str_by_capital_letters(item):
    # upper the first letter
    item = item[0].upper() + item[1:]
    # transform 'Service' to 'service', 'CronJob' to 'cron_job', 'TargetPort' to 'target_port', etc.
    return '_'.join(re.findall('[A-Z][^A-Z]*', item)).lower()


class Provisioner:
    def __init__(self, command, sync_mode):
        self.command = command
        self.sync_mode = sync_mode

    @staticmethod
    def _replicas_are_equal(replicas):
        replicas = [0 if r is None else r for r in replicas]  # replace all None to 0
        return all(r == replicas[0] for r in replicas)

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
    def _get_template_context(file_path):
        with open(file_path) as f:
            try:
                context = yaml.load(f.read())
            except Exception as e:
                raise RuntimeError('Unable to load yaml file: {}, {}'.format(file_path, e))
            if context is None:
                raise RuntimeError('File "{}" is empty'.format(file_path))
            if 'kind' not in context or context['kind'] is None:
                raise RuntimeError('Field "kind" not found (or empty) in file "{}"'.format(file_path))
            if 'metadata' not in context or context['metadata'] is None:
                raise RuntimeError('Field "metadata" not found (or empty) in file "{}"'.format(file_path))
            if 'name' not in context['metadata'] or context['metadata']['name'] is None:
                raise RuntimeError('Field "metadata->name" not found (or empty) in file "{}"'.format(file_path))
            if 'spec' in context:
                # INFO: Set replicas = 1 by default for replaces cases in Deployment and StatefulSet
                if 'replicas' not in context['spec'] or context['spec']['replicas'] is None:
                    if context['kind'] in ['Deployment', 'StatefulSet']:
                        context['spec']['replicas'] = 1
            return context

    @staticmethod
    def _port_obj_to_str(port):
        if hasattr(port, 'name') and hasattr(port, 'port'):
            return '{} ({})'.format(port.name, port.port)
        return '{}'.format(port.port)

    def _notify_about_missing_items_in_template(self, items, missing_type):
        skull = """
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
            self._deploy(file_path)
        if self.command == 'destroy':
            self._destroy(file_path)

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

    def _deploy(self, file_path):
        template_body = self._get_template_context(file_path)
        kube_client = Adapter(template_body)

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
                self._is_pvc_specs_equals(resource.spec, template_body['spec'])

            if template_body['kind'] == 'PersistentVolume':
                resource = kube_client.get()
                if resource.status.phase in ['Bound', 'Released']:
                    log.warning('PersistentVolume has "{}" status, skip replacing'.format(resource.status.phase))

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

    def _destroy(self, file_path):
        template_body = self._get_template_context(file_path)
        kube_client = Adapter(template_body)
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

    def _wait_deployment_complete(self, kube_client, tries, timeout):
        for i in range(0, tries):
            sleep(timeout)
            status = kube_client.get().status

            replicas = [kube_client.replicas, status.replicas, status.available_replicas,
                        status.ready_replicas, status.updated_replicas]

            log.info('desiredReplicas = {}, updatedReplicas = {}, availableReplicas = {}'.
                     format(replicas[0], replicas[4], replicas[2]))
            if self._replicas_are_equal(replicas) and status.unavailable_replicas is None:
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
                if self._replicas_are_equal(replicas):
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
            if self._replicas_are_equal(replicas) and status.number_unavailable is None:
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
        if api_version == 'test/test':
            return K8sClientMock(self.name)

    @staticmethod
    def _get_app_kind(kind):
        if kind not in ['ConfigMap', 'CronJob', 'DaemonSet', 'Deployment', 'Endpoints',
                        'Ingress', 'Job', 'Namespace', 'PodDisruptionBudget', 'ResourceQuota',
                        'Secret', 'Service', 'ServiceAccount', 'StatefulSet', 'StorageClass',
                        'PersistentVolume', 'PersistentVolumeClaim', ]:
            raise RuntimeError('Unknown kind "{}" in generated file'.format(kind))

        return _split_str_by_capital_letters(kind)

    def get(self):
        try:
            if self.kind in ['namespace', 'storage_class', 'persistent_volume', ]:
                response = getattr(self.api, 'read_{}'.format(self.kind))(self.name)
            else:
                response = getattr(self.api, 'read_namespaced_{}'.format(self.kind))(
                    self.name, namespace=self.namespace)
        except ApiException as e:
            if e.reason == 'Not Found':
                return None
            log.error('Exception when calling "read_namespaced_{}": {}'.format(self.kind, self._add_indent(e.body)))
            raise ProvisioningError(e)

        return response

    def create(self):
        try:
            if self.kind in ['namespace', 'storage_class', 'persistent_volume', ]:
                return getattr(self.api, 'create_{}'.format(self.kind))(body=self.body)
            return getattr(self.api, 'create_namespaced_{}'.format(self.kind))(
                body=self.body, namespace=self.namespace)
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
            if self.kind in ['service', ]:
                if ports is not None:
                    self.body['spec']['ports'] = ports
                return getattr(self.api, 'patch_namespaced_{}'.format(self.kind))(
                    name=self.name, body=self.body, namespace=self.namespace
                )

            if self.kind in ['namespace', 'storage_class', 'persistent_volume', ]:
                return getattr(self.api, 'replace_{}'.format(self.kind))(
                    name=self.name, body=self.body)

            return getattr(self.api, 'replace_namespaced_{}'.format(self.kind))(
                name=self.name, body=self.body, namespace=self.namespace)
        except ApiException as e:
            log.error('Exception when calling "replace_namespaced_{}": {}'.format(self.kind, self._add_indent(e.body)))
            raise ProvisioningError(e)

    def delete(self):
        try:
            if self.kind in ['service', ]:
                return self.api.delete_namespaced_service(name=self.name, namespace=self.namespace,
                                                          body=client.V1DeleteOptions(propagation_policy='Fore'))
            if self.kind in ['namespace', 'storage_class', 'persistent_volume']:
                return getattr(self.api, 'delete_{}'.format(self.kind))(
                    name=self.name, body=client.V1DeleteOptions(propagation_policy='Foreground'))

            return getattr(self.api, 'delete_namespaced_{}'.format(self.kind))(
                name=self.name, body=client.V1DeleteOptions(propagation_policy='Foreground'),
                namespace=self.namespace)
        except ApiException as e:
            if e.reason == 'Not Found':
                return None
            log.error('Exception when calling "delete_namespaced_{}": {}'.format(self.kind, self._add_indent(e.body)))
            raise ProvisioningError(e)

    @staticmethod
    def _add_indent(json_str):
        try:
            return json.dumps(json.loads(json_str), indent=4)
        except:     # NOQA
            return json_str
