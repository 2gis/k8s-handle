import numbers
import os
import re

from kubernetes import client

import settings
from common import dictionary, filesystem
from templating import b64decode

INCLUDE_RE = re.compile('{{\s?file\s?=\s?\'(?P<file>[^\']*)\'\s?}}')
CUSTOM_ENV_RE = re.compile('^(?P<prefix>.*){{\s*env\s*=\s*\'(?P<env>[^\']*)\'\s*}}(?P<postfix>.*)$')  # noqa


class InvalidYamlException(Exception):
    pass


def get_client_config(context):
    c = client.Configuration()
    c.host = context.get('k8s_master_uri')
    c.api_key = {"authorization": "Bearer " + context.get('k8s_token')}
    c.ssl_ca_cert = filesystem.file_write_temporary(
        b64decode(context.get('k8s_ca_base64')).encode('utf-8')
    )

    if 'k8s_handle_debug' in context:
        if context['k8s_handle_debug'] is True \
                or context['k8s_handle_debug'] == 'true' \
                or context['k8s_handle_debug'] == 'True':
            c.debug = True

    return c


def context_load(section):
    if section == settings.COMMON_SECTION_NAME:
        raise RuntimeError('Section "{}" is not intended to deploy'.format(settings.COMMON_SECTION_NAME))

    try:
        context = filesystem.file_load_yaml(settings.CONFIG_FILE)
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
        context = dictionary.merge(
            context[settings.COMMON_SECTION_NAME],
            context[section]
        )

    if 'templates' not in context and 'kubectl' not in context:
        raise RuntimeError(
            'Section "templates" or "kubectl" not found in config file "{}"'.format(
                settings.CONFIG_FILE
            )
        )

    # check if keys contain dashes
    dashed_keys = [key for key in dictionary.keys_nested(context) if '-' in key]

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
        return filesystem.file_load_yaml(match.groupdict().get('file'))

    match = CUSTOM_ENV_RE.match(variable)

    if match:
        if os.environ.get(match.groupdict().get('env')):
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
