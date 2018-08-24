import atexit
import copy
import logging
import numbers
import os
import re
import tempfile

import yaml
from kubernetes import client

import settings
from templating import b64decode

log = logging.getLogger(__name__)

INCLUDE_RE = re.compile('{{\s?file\s?=\s?\'(?P<file>[^\']*)\'\s?}}')
CUSTOM_ENV_RE = re.compile('^(?P<prefix>.*){{\s*env\s*=\s*\'(?P<env>[^\']*)\'\s*}}(?P<postfix>.*)$')  # noqa


class InvalidYamlException(Exception):
    pass


def get_client_config(context):
    c = client.Configuration()
    c.host = context.get('k8s_master_uri')
    c.ssl_ca_cert = _write_tmp_file(b64decode(context.get('k8s_ca_base64')).encode('utf-8'))
    c.api_key = {"authorization": "Bearer " + context.get('k8s_token')}

    if 'k8s_handle_debug' in context:
        if context['k8s_handle_debug'] is True \
                or context['k8s_handle_debug'] == 'true' \
                or context['k8s_handle_debug'] == 'True':
            c.debug = True

    return c


def load_context_section(section):
    if section == settings.COMMON_SECTION_NAME:
        raise RuntimeError('Section "{}" is not intended to deploy'.format(settings.COMMON_SECTION_NAME))

    try:
        with open(settings.CONFIG_FILE) as f:
            context = yaml.load(f.read())

    except Exception as e:
        raise InvalidYamlException(e)

    if context is None:
        raise RuntimeError('Config file "{}" is empty'.format(settings.CONFIG_FILE))

    if section and section not in context:
        raise RuntimeError('Section "{}" not found in config file "{}"'.format(section, settings.CONFIG_FILE))

    # delete all sections except common and used section
    context = {key: context[key] for key in [settings.COMMON_SECTION_NAME, section]}
    context = _update_context_recursively(context)

    if section and section in context:
        context = _merge_options(context[settings.COMMON_SECTION_NAME], context[section])

    settings.K8S_NAMESPACE = context.get('k8s_namespace')

    if 'templates' not in context and 'kubectl' not in context:
        raise RuntimeError(
            'Section "templates" or "kubectl" not found in config file "{}"'.format(settings.CONFIG_FILE))

    # check if keys contain dashes
    dashed_keys = [key for key in _nested_keys(context) if '-' in key]

    if dashed_keys:
        raise RuntimeError(
            'Variable names should never include dashes, '
            'check your vars, please: {}'.format(
                ', '.join(sorted(dashed_keys))
            )
        )

    return context


def _update_context_recursively(context):
    if isinstance(context, dict):
        output = {}

        for key, value in context.items():
            if isinstance(value, str):
                output[key] = _process_variable(value)
                continue

            if isinstance(value, numbers.Number):
                output[key] = value
                continue

            output[key] = _update_context_recursively(value)

        return output

    if isinstance(context, list):
        output = []

        for value in context:
            if isinstance(value, str):
                output.append(_process_variable(value))
                continue

            if isinstance(value, numbers.Number):
                output.append(value)
                continue

            output.append(_update_context_recursively(value))

        return output

    return context


def _process_variable(variable):
    match = INCLUDE_RE.match(variable)

    if match:
        with open(match.groupdict().get('file'), 'r') as f:
            return yaml.load(f.read())

    match = CUSTOM_ENV_RE.match(variable)

    if match:
        if os.environ.get(match.groupdict().get('env')) is not None:
            return "{}{}{}".format(
                match.groupdict().get('prefix'),
                os.environ.get(match.groupdict().get('env')),
                match.groupdict().get('postfix')
            )

        if settings.GET_ENVIRON_STRICT:
            raise RuntimeError(
                'Environment variable "{}" is not set'.format(
                    match.groupdict().get('env')
                )
            )

    return variable


# helpers; probably should be moved to a separate file later

def _write_tmp_file(data):
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write(data)
    f.flush()
    atexit.register(_remove_file, f.name)
    return f.name


def _remove_file(file_path):
    try:
        os.remove(file_path)
    except Exception as e:
        log.warning('Unable to remove "{}", due to "{}"'.format(file_path, e))


def _merge_options(base, rewrites):
    base = copy.deepcopy(base)

    for key, value in rewrites.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _merge_options(base[key], value)
            continue

        base[key] = value

    return base


def _nested_keys(dictionary):
    result = []

    for key, value in dictionary.items():
        result.append(key)

        if not isinstance(value, dict):
            result += _nested_keys(value)

    return list(set(result))
