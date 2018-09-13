import os
import re
import yaml
import atexit
import settings
import tempfile
import logging
import copy

from kubernetes import client
from templating import b64decode

log = logging.getLogger(__name__)


INCLUDE_RE = re.compile('{{\s?file\s?=\s?\'(?P<file>[^\']*)\'\s?}}')
CUSTOM_ENV_RE = re.compile('^(?P<prefix>.*){{\s*env\s*=\s*\'(?P<env>[^\']*)\'\s*}}(?P<postfix>.*)$')    # noqa


class InvalidYamlException(Exception):
    pass


def get_client_config(context):
    c = client.Configuration()
    c.host = context.get('k8s_master_uri')
    c.ssl_ca_cert = write_tmp_file(b64decode(context.get('k8s_ca_base64')).encode('utf-8'))
    c.api_key = {"authorization": "Bearer " + context.get('k8s_token')}
    if 'k8s_handle_debug' in context:
        if context['k8s_handle_debug'] is True \
                or context['k8s_handle_debug'] == 'true' \
                or context['k8s_handle_debug'] == 'True':
            c.debug = True
    return c


def _load_context_from_file(path):
    with open(path) as f:
        try:
            return yaml.load(f.read())
        except Exception as e:
            raise InvalidYamlException(e)


def _process_variable(variable):
    matches = INCLUDE_RE.match(variable)
    if matches is not None:
        config_file = matches.groupdict().get('file')
        with open(config_file, 'r') as f:
            include = yaml.load(f.read())
            return include
    matches = CUSTOM_ENV_RE.match(variable)
    if matches is not None:
        prefix = matches.groupdict().get('prefix')
        env_var_name = matches.groupdict().get('env')
        postfix = matches.groupdict().get('postfix')
        if os.environ.get(env_var_name) is None and settings.GET_ENVIRON_STRICT:
            raise RuntimeError('Environment variable "{}" is not set'.format(env_var_name))
        return prefix + os.environ.get(env_var_name, '') + postfix
    return variable


def _merge_options(base, rewrites):
    result = copy.deepcopy(base)
    for key, value in rewrites.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_options(result[key], value)
        else:
            result[key] = value

    return result


def _update_context_recursively(context, depth=0):
    if depth > settings.MAX_CONFIG_INCLUDE_DEPTH:
        raise RuntimeError('Max include depth for config has reached')

    if isinstance(context, dict):
        output = {}
        for key, value in context.items():
            if isinstance(value, str):
                output[key] = _update_context_recursively(_process_variable(value), depth + 1)
            else:
                output[key] = _update_context_recursively(value)
        return output
    elif isinstance(context, list):
        output = []
        for value in context:
            if isinstance(value, str):
                output.append(_update_context_recursively(_process_variable(value), depth + 1))
            else:
                output.append(_update_context_recursively(value))
        return output
    else:
        return context


def load_context_section(section):
    if section == settings.COMMON_SECTION_NAME:
        raise RuntimeError('Section "{}" is not intended to deploy'.format(settings.COMMON_SECTION_NAME))
    context = _load_context_from_file(settings.CONFIG_FILE)
    if context is None:
        raise RuntimeError('Config file "{}" is empty'.format(settings.CONFIG_FILE))
    if section and section not in context:
        raise RuntimeError('Section "{}" not found in config file "{}"'.format(section, settings.CONFIG_FILE))

    # delete all sections except common and used section
    context = {key: context[key] for key in ['common', section]}
    context = _update_context_recursively(context)
    if section and section in context:
        context = _merge_options(context[settings.COMMON_SECTION_NAME], context[section])

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


def check_required_vars(context_dict, required_vars):
    missing_vars = []
    for v in required_vars:
        if v not in context_dict or context_dict[v] == '' or context_dict[v] is None:
            missing_vars.append(v)

    if len(missing_vars) != 0:
        raise RuntimeError(
            'Variables "{}" not found (or empty) in config file "{}". '
            'Please, set all required variables: {}.'.format(', '.join(missing_vars), settings.CONFIG_FILE,
                                                             ', '.join(required_vars)))


def remove_file(file_path):
    try:
        os.remove(file_path)
    except Exception as e:
        log.warning('Unable to remove "{}", due to "{}"'.format(file_path, e))
        pass


def write_tmp_file(data):
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write(data)
    f.flush()
    atexit.register(remove_file, f.name)
    return f.name
