import logging
from time import sleep

from kubernetes.client.models.v1_label_selector import V1LabelSelector
from kubernetes.client.models.v1_label_selector_requirement import V1LabelSelectorRequirement
from kubernetes.client.models.v1_resource_requirements import V1ResourceRequirements

from k8s_handle import settings
from k8s_handle.templating import get_template_contexts
from k8s_handle.transforms import split_str_by_capital_letters
from .adapters import Adapter
from .warning_handler import WarningHandler

log = logging.getLogger(__name__)


class Provisioner:
    def __init__(self, command, sync_mode, show_logs):
        self.command = command
        self.sync_mode = False if show_logs else sync_mode
        self.show_logs = show_logs
        self._warning_handler = WarningHandler()

    @staticmethod
    def _replicas_count_are_equal(replicas):
        replicas = [0 if r is None else r for r in replicas]  # replace all None to 0
        return all(r == replicas[0] for r in replicas)

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

    def run(self, file_path):
        if self.command == 'deploy':
            self._deploy_all(file_path)
        if self.command == 'destroy':
            self._destroy_all(file_path)

    def _is_pvc_specs_equals(self, old_obj, new_dict):
        for new_key in new_dict.keys():
            old_key = split_str_by_capital_letters(new_key)

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
        kube_client = Adapter.get_instance(template_body, warning_handler=self._warning_handler)

        if not kube_client:
            raise RuntimeError(
                'Unknown apiVersion "{}" in template "{}"'.format(
                    template_body['apiVersion'],
                    file_path
                )
            )

        log.info('Using namespace "{}"'.format(kube_client.namespace))
        resource = kube_client.get()

        if resource is None:
            log.info('{} "{}" does not exist, create it'.format(template_body['kind'], kube_client.name))
            kube_client.create()
        else:
            log.info('{} "{}" already exists, replace it'.format(template_body['kind'], kube_client.name))
            parameters = {}

            if hasattr(resource, 'metadata'):
                if hasattr(resource.metadata, 'resource_version'):
                    parameters['resourceVersion'] = resource.metadata.resource_version
            elif 'metadata' in resource:
                if 'resourceVersion' in resource['metadata']:
                    parameters['resourceVersion'] = resource['metadata']['resourceVersion']

            if template_body['kind'] == 'Service':
                if hasattr(resource.spec, 'cluster_ip'):
                    parameters['clusterIP'] = resource.spec.cluster_ip

            if template_body['kind'] == 'PersistentVolumeClaim':
                if self._is_pvc_specs_equals(resource.spec, template_body['spec']):
                    log.info('PersistentVolumeClaim is not changed')
                    return

            if template_body['kind'] == 'PersistentVolume':
                if resource.status.phase in ['Bound', 'Released']:
                    log.warning('PersistentVolume has "{}" status, skip replacing'.format(resource.status.phase))
                    return

            kube_client.replace(parameters)

        if self.sync_mode:
            if template_body['kind'] == 'Deployment':
                self._wait_deployment_complete(kube_client,
                                               tries=settings.CHECK_STATUS_TRIES,
                                               timeout=settings.CHECK_STATUS_TIMEOUT)

            if template_body['kind'] == 'StatefulSet':
                self._wait_statefulset_complete(kube_client,
                                                tries=settings.CHECK_STATUS_TRIES,
                                                timeout=settings.CHECK_STATUS_TIMEOUT)

            # INFO: vadim.reyder Since Kubernetes version 1.6 all DaemonSets by default have
            # `updateStrategy.type`=`RollingUpdate`, so we wait for deploy only if `updateStrategy.type` != 'OnDelete'.
            # WARNING: We consciously skip case with kubernetes version < 1.6, due to it's very old.
            if template_body['kind'] == 'DaemonSet' and \
                    template_body.get('spec').get('updateStrategy', {}).get('type') != 'OnDelete':
                self._wait_daemonset_complete(kube_client,
                                              tries=settings.CHECK_STATUS_TRIES,
                                              timeout=settings.CHECK_STATUS_TIMEOUT)

            if template_body['kind'] == 'Job':
                return self._wait_job_complete(kube_client,
                                               tries=settings.CHECK_STATUS_TRIES,
                                               timeout=settings.CHECK_STATUS_TIMEOUT)

        if template_body['kind'] == 'Job' and self.show_logs:
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
        kube_client = Adapter.get_instance(template_body, warning_handler=self._warning_handler)

        if not kube_client:
            raise RuntimeError(
                'Unknown apiVersion "{}" in template "{}"'.format(
                    template_body['apiVersion'],
                    file_path
                )
            )

        log.info('Using namespace "{}"'.format(kube_client.namespace))
        log.info('Trying to delete {} "{}"'.format(template_body['kind'], kube_client.name))
        response = kube_client.delete()

        if response is None:
            log.info("{} {} is not found".format(template_body['kind'], kube_client.name))
            return

        # custom objects api response is a simple dictionary without message field
        if hasattr(response, 'message') and response.message is not None:
            raise RuntimeError('{} "{}" deletion failed: {}'.format(
                template_body['kind'], kube_client.name, response.message))

        if isinstance(response, dict) and not response.get('metadata', {}).get('deletionTimestamp'):
            raise RuntimeError('{} "{}" deletion failed: {}'.format(template_body['kind'], kube_client.name, response))

        if self.sync_mode:
            self._wait_destruction_complete(kube_client, template_body['kind'],
                                            tries=settings.CHECK_STATUS_TRIES,
                                            timeout=settings.CHECK_STATUS_TIMEOUT)

        log.info('{} "{}" has been deleted'.format(template_body['kind'], kube_client.name))

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
            deployment = kube_client.get()
            status = deployment.status

            replicas = [deployment.spec.replicas, status.replicas, status.available_replicas,
                        status.ready_replicas, status.updated_replicas]

            log.info('desiredReplicas = {}, updatedReplicas = {}, availableReplicas = {}'.
                     format(replicas[0], replicas[4], replicas[2]))
            if self._replicas_count_are_equal(replicas) and status.unavailable_replicas is None:
                log.info('Deployment completed on {} attempt'.format(i + 1))
                return
            else:
                log.info('Deployment not completed on {} attempt, next attempt in {} sec.'.format(i + 1, timeout))

        raise RuntimeError('Deployment not completed for {} tries'.format(tries))

    def _wait_statefulset_complete(self, kube_client, tries, timeout):
        for i in range(0, tries):
            sleep(timeout)
            statefulset = kube_client.get()
            status = statefulset.status

            current_revision = status.current_revision
            update_revision = status.update_revision
            replicas = [statefulset.spec.replicas, status.current_replicas, status.ready_replicas]

            log.info('Current revision {}, should be {}'.format(current_revision, update_revision))
            if current_revision == update_revision:
                log.info('desiredReplicas = {}, updatedReplicas = {}, availableReplicas = {}'.
                         format(replicas[0], replicas[1], replicas[2]))
                if self._replicas_count_are_equal(replicas):
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
            if self._replicas_count_are_equal(replicas) and status.number_unavailable is None:
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
