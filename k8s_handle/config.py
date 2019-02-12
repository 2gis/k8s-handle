import copy
import logging
import os
import re

from kubernetes import client

from k8s_handle import settings
from k8s_handle.dictionary import merge
from k8s_handle.filesystem import load_yaml, write_file_tmp
from k8s_handle.templating import b64decode

log = logging.getLogger(__name__)

INCLUDE_RE = re.compile(r'{{\s?file\s?=\s?\'(?P<file>[^\']*)\'\s?}}')
CUSTOM_ENV_RE = r'{{\s*env\s*=\s*\'([^\']*)\'\s*}}'

KEY_USE_KUBECONFIG = 'use_kubeconfig'
KEY_K8S_MASTER_URI = 'k8s_master_uri'
KEY_K8S_MASTER_URI_ENV = KEY_K8S_MASTER_URI.upper()
KEY_K8S_MASTER_URI_ENV_DEPRECATED = 'K8S_HOST'

KEY_K8S_CA_BASE64 = 'k8s_ca_base64'
KEY_K8S_CA_BASE64_ENV = KEY_K8S_CA_BASE64.upper()
KEY_K8S_CA_BASE64_URI_ENV_DEPRECATED = 'K8S_CA'

KEY_K8S_TOKEN = 'k8s_token'
KEY_K8S_TOKEN_ENV = KEY_K8S_TOKEN.upper()

KEY_K8S_NAMESPACE = 'k8s_namespace'
KEY_K8S_NAMESPACE_ENV = KEY_K8S_NAMESPACE.upper()
KEY_K8S_HANDLE_DEBUG = 'k8s_handle_debug'


class PriorityEvaluator:
    def __init__(self, cli_arguments, context_arguments, environment):
        self.cli_arguments = cli_arguments
        self.context_arguments = context_arguments
        self.environment = environment
        self.loaded = False

    def k8s_namespace_default(self, kubeconfig_namespace=None):
        return PriorityEvaluator._first(
            self.context_arguments.get(KEY_K8S_NAMESPACE),
            kubeconfig_namespace,
            self.environment.get(KEY_K8S_NAMESPACE_ENV))

    def k8s_client_configuration(self):
        for parameter, value in {
            KEY_K8S_MASTER_URI: self._k8s_master_uri(),
            KEY_K8S_CA_BASE64: self._k8s_ca_base64(),
            KEY_K8S_TOKEN: self._k8s_token()
        }.items():
            if value:
                continue

            raise RuntimeError(
                '{0} parameter is not set. Please, provide {0} via CLI, config or env.'.format(parameter))

        configuration = client.Configuration()
        configuration.host = self._k8s_master_uri()
        configuration.ssl_ca_cert = write_file_tmp(b64decode(self._k8s_ca_base64()).encode('utf-8'))
        configuration.api_key = {"authorization": "Bearer " + self._k8s_token()}
        configuration.debug = self._k8s_handle_debug()
        return configuration

    def environment_deprecated(self):
        return self.environment.get(KEY_K8S_MASTER_URI_ENV_DEPRECATED) or \
               self.environment.get(KEY_K8S_CA_BASE64_URI_ENV_DEPRECATED)

    def _k8s_master_uri(self):
        return PriorityEvaluator._first(
            self.cli_arguments.get(KEY_K8S_MASTER_URI),
            self.context_arguments.get(KEY_K8S_MASTER_URI),
            self.environment.get(KEY_K8S_MASTER_URI_ENV),
            self.environment.get(KEY_K8S_MASTER_URI_ENV_DEPRECATED))

    def _k8s_ca_base64(self):
        return PriorityEvaluator._first(
            self.cli_arguments.get(KEY_K8S_CA_BASE64),
            self.context_arguments.get(KEY_K8S_CA_BASE64),
            self.environment.get(KEY_K8S_CA_BASE64_ENV),
            self.environment.get(KEY_K8S_CA_BASE64_URI_ENV_DEPRECATED))

    def _k8s_token(self):
        return PriorityEvaluator._first(
            self.cli_arguments.get(KEY_K8S_TOKEN),
            self.context_arguments.get(KEY_K8S_TOKEN),
            self.environment.get(KEY_K8S_TOKEN_ENV))

    def _k8s_handle_debug(self):
        return PriorityEvaluator._first(
            self.cli_arguments.get(KEY_K8S_HANDLE_DEBUG),
            self.context_arguments.get(KEY_K8S_HANDLE_DEBUG) in [True, 'true', 'True'])

    @staticmethod
    def _first(*arguments):
        if not arguments:
            return None

        for argument in arguments:
            if not argument:
                continue

            return argument

        return None


def _process_variable(variable):
    matches = INCLUDE_RE.match(variable)

    if matches:
        return load_yaml(matches.groupdict().get('file'))

    try:
        return re.sub(CUSTOM_ENV_RE, lambda m: os.environ[m.group(1)], variable)

    except KeyError as err:
        log.debug('Environment variable "{}" is not set'.format(err.args[0]))
        if settings.GET_ENVIRON_STRICT:
            raise RuntimeError('Environment variable "{}" is not set'.format(err.args[0]))

    return re.sub(CUSTOM_ENV_RE, lambda m: os.environ.get(m.group(1), ''), variable)


def _update_single_variable(value, include_history):
    if value in include_history:
        raise RuntimeError('Infinite include loop')

    local_history = copy.copy(include_history)
    local_history.append(value)

    return _update_context_recursively(_process_variable(value), local_history)


def _update_context_recursively(context, include_history=[]):
    if isinstance(context, dict):
        output = {}
        for key, value in context.items():
            if isinstance(value, str):
                output[key] = _update_single_variable(value, include_history)
            else:
                output[key] = _update_context_recursively(value)
        return output
    elif isinstance(context, list):
        output = []
        for value in context:
            if isinstance(value, str):
                output.append(_update_single_variable(value, include_history))
            else:
                output.append(_update_context_recursively(value))
        return output
    else:
        return context


def load_context_section(section):
    if not section:
        raise RuntimeError('Empty section specification is not allowed')

    if section == settings.COMMON_SECTION_NAME:
        raise RuntimeError('Section "{}" is not intended to deploy'.format(settings.COMMON_SECTION_NAME))

    context = load_yaml(settings.CONFIG_FILE)

    if context is None:
        raise RuntimeError('Config file "{}" is empty'.format(settings.CONFIG_FILE))

    if section not in context:
        raise RuntimeError('Section "{}" not found in config file "{}"'.format(section, settings.CONFIG_FILE))

    # delete all sections except common and used section
    context.setdefault(settings.COMMON_SECTION_NAME, {})
    context = {key: context[key] for key in [settings.COMMON_SECTION_NAME, section]}
    context = _update_context_recursively(context)

    if section and section in context:
        context = merge(context[settings.COMMON_SECTION_NAME], context[section])

    if 'templates' not in context and 'kubectl' not in context:
        raise RuntimeError(
            'Section "templates" or "kubectl" not found in config file "{}"'.format(settings.CONFIG_FILE))

    validate_dashes(context)
    return context


def get_all_nested_keys(result, d):
    for key, value in d.items():
        result.append(key)
        if isinstance(d[key], dict):
            get_all_nested_keys(result, d[key])

    return result


def get_vars_with_dashes(vars_list):
    return [var_name for var_name in vars_list if '-' in var_name]


def validate_dashes(context):
    all_keys = get_all_nested_keys([], context)
    dashes = get_vars_with_dashes(all_keys)
    if len(dashes) != 0:
        raise RuntimeError('Variable names should never include dashes, '
                           'check your vars, please: {}'.format(', '.join(sorted(dashes))))
