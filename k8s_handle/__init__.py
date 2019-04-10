#!/usr/bin/env python

import argparse
import logging
import os
import sys

from kubernetes import client
from kubernetes.config import list_kube_config_contexts, load_kube_config

from k8s_handle import config
from k8s_handle import settings
from k8s_handle import templating
from k8s_handle.exceptions import DeprecationError, ProvisioningError
from k8s_handle.filesystem import InvalidYamlError
from k8s_handle.k8s.deprecation_checker import ApiDeprecationChecker
from k8s_handle.k8s.provisioner import Provisioner

COMMAND_DEPLOY = 'deploy'
COMMAND_DESTROY = 'destroy'

log = logging.getLogger(__name__)
logging.basicConfig(level=settings.LOG_LEVEL, format=settings.LOG_FORMAT, datefmt=settings.LOG_DATE_FORMAT)


def handler_deploy(args):
    _handler_deploy_destroy(args, COMMAND_DEPLOY)


def handler_destroy(args):
    _handler_deploy_destroy(args, COMMAND_DESTROY)


def handler_apply(args):
    _handler_apply_delete(args, COMMAND_DEPLOY)


def handler_delete(args):
    _handler_apply_delete(args, COMMAND_DESTROY)


def handler_render(args):
    context = config.load_context_section(args.get('section'))
    templating.Renderer(
        settings.TEMPLATES_DIR,
        args.get('tags'),
        args.get('skip_tags')
    ).generate_by_context(context)


def _handler_deploy_destroy(args, command):
    context = config.load_context_section(args.get('section'))
    resources = templating.Renderer(
        settings.TEMPLATES_DIR,
        args.get('tags'),
        args.get('skip_tags')
    ).generate_by_context(context)

    if args.get('dry_run'):
        return

    _handler_provision(
        command,
        resources,
        config.PriorityEvaluator(args, context, os.environ),
        args.get('use_kubeconfig'),
        args.get('sync_mode'),
        args.get('show_logs')
    )


def _handler_apply_delete(args, command):
    _handler_provision(
        command,
        [os.path.join(settings.TEMP_DIR, args.get('resource'))],
        config.PriorityEvaluator(args, {}, os.environ),
        args.get('use_kubeconfig'),
        args.get('sync_mode'),
        args.get('show_logs')
    )


def _handler_provision(command, resources, priority_evaluator, use_kubeconfig, sync_mode, show_logs):
    kubeconfig_namespace = None

    if priority_evaluator.environment_deprecated():
        log.warning("K8S_HOST and K8S_CA environment variables support is deprecated "
                    "and will be discontinued in the future. Use K8S_MASTER_URI and K8S_CA_BASE64 instead.")

    # INFO rvadim: https://github.com/kubernetes-client/python/issues/430#issuecomment-359483997
    if use_kubeconfig:
        try:
            load_kube_config()
            kubeconfig_namespace = list_kube_config_contexts()[1].get('context').get('namespace')
        except Exception as e:
            raise RuntimeError(e)
    else:
        client.Configuration.set_default(priority_evaluator.k8s_client_configuration())

    settings.K8S_NAMESPACE = priority_evaluator.k8s_namespace_default(kubeconfig_namespace)
    log.info('Default namespace "{}"'.format(settings.K8S_NAMESPACE))

    if not settings.K8S_NAMESPACE:
        log.info("Default namespace is not set. "
                 "This may lead to provisioning error, if namespace is not set for each resource.")

    d = ApiDeprecationChecker(client.VersionApi().get_code().git_version[1:])
    p = Provisioner(command, sync_mode, show_logs)

    for resource in resources:
        d.run(resource)

    for resource in resources:
        p.run(resource)


parser = argparse.ArgumentParser(description='CLI utility generate k8s resources by templates and apply it to cluster')
subparsers = parser.add_subparsers(dest="command")
subparsers.required = True

parser_target_config = argparse.ArgumentParser(add_help=False)
parser_target_config.add_argument('-s', '--section', required=True, type=str, help='Section to deploy from config file')
parser_target_config.add_argument('-c', '--config', required=False, help='Config file, default: config.yaml')
parser_target_config.add_argument('--tags', action='append', required=False,
                                  help='Only use templates tagged with these values')
parser_target_config.add_argument('--skip-tags', action='append', required=False,
                                  help='Only use templates whose tags do not match these values')

parser_target_resource = argparse.ArgumentParser(add_help=False)
parser_target_resource.add_argument('-r', '--resource', required=True, type=str,
                                    help='Resource spec path, absolute (started with slash) or relative from TEMP_DIR')

parser_deprecated = argparse.ArgumentParser(add_help=False)
parser_deprecated.add_argument('--dry-run', required=False, action='store_true',
                               help='Don\'t run kubectl commands. Deprecated, use "k8s-handle template" instead')

parser_provisioning = argparse.ArgumentParser(add_help=False)
parser_provisioning.add_argument('--sync-mode', action='store_true', required=False, default=False,
                                 help='Turn on sync mode and wait deployment ending')
parser_provisioning.add_argument('--tries', type=int, required=False, default=360,
                                 help='Count of tries to check deployment status')
parser_provisioning.add_argument('--retry-delay', type=int, required=False, default=5,
                                 help='Sleep between tries in seconds')
parser_provisioning.add_argument('--strict', action='store_true', required=False,
                                 help='Check existence of all env variables in config.yaml and stop if var is not set')
parser_provisioning.add_argument('--use-kubeconfig', action='store_true', required=False,
                                 help='Try to use kube config')
parser_provisioning.add_argument('--k8s-handle-debug', action='store_true', required=False,
                                 help='Show K8S client debug messages')

parser_logs = argparse.ArgumentParser(add_help=False)
parser_logs.add_argument('--show-logs', action='store_true', required=False, default=False, help='Show logs for jobs')
parser_logs.add_argument('--tail-lines', type=int, required=False, help='Lines of recent log file to display')

arguments_connection = parser_provisioning.add_argument_group()
arguments_connection.add_argument('--k8s-master-uri', required=False, help='K8S master to connect to')
arguments_connection.add_argument('--k8s-ca-base64', required=False, help='base64-encoded K8S certificate authority')
arguments_connection.add_argument('--k8s-token', required=False, help='K8S token to use')

parser_deploy = subparsers.add_parser(
    'deploy',
    parents=[parser_provisioning, parser_target_config, parser_logs, parser_deprecated],
    help='Do attempt to create specs from templates and deploy K8S resources of the selected section')
parser_deploy.set_defaults(func=handler_deploy)

parser_apply = subparsers.add_parser('apply', parents=[parser_provisioning, parser_target_resource, parser_logs],
                                     help='Do attempt to deploy K8S resource from the existing spec')
parser_apply.set_defaults(func=handler_apply)

parser_destroy = subparsers.add_parser('destroy',
                                       parents=[parser_provisioning, parser_target_config, parser_deprecated],
                                       help='Do attempt to destroy K8S resources of the selected section')
parser_destroy.set_defaults(func=handler_destroy)

parser_delete = subparsers.add_parser('delete', parents=[parser_provisioning, parser_target_resource],
                                      help='Do attempt to destroy K8S resource from the existing spec')
parser_delete.set_defaults(func=handler_delete)

parser_template = subparsers.add_parser('render', parents=[parser_target_config],
                                        help='Make resources from the template and config. '
                                             'Created resources will be placed into the TEMP_DIR')
parser_template.set_defaults(func=handler_render)


def main():
    # INFO furiousassault: backward compatibility rough attempt
    # must be removed later according to https://github.com/2gis/k8s-handle/issues/40
    deprecation_warnings = 0
    filtered_arguments = []

    for argument in sys.argv[1:]:
        if argument in ['--sync-mode=true', '--sync-mode=True', '--dry-run=true', '--dry-run=True']:
            deprecation_warnings += 1
            filtered_arguments.append(argument.split('=')[0])
            continue

        if argument in ['--sync-mode=false', '--sync-mode=False', '--dry-run=false', '--dry-run=False']:
            deprecation_warnings += 1
            continue

        filtered_arguments.append(argument)

    args, unrecognized_args = parser.parse_known_args(filtered_arguments)

    if deprecation_warnings or unrecognized_args:
        log.warning("Explicit true/false arguments to --sync-mode and --dry-run keys are deprecated "
                    "and will be discontinued in the future. Use these keys without arguments instead.")

    args_dict = vars(args)
    settings.CHECK_STATUS_TRIES = args_dict.get('tries')
    settings.CHECK_DAEMONSET_STATUS_TRIES = args_dict.get('tries')
    settings.CHECK_STATUS_TIMEOUT = args_dict.get('retry_delay')
    settings.CHECK_DAEMONSET_STATUS_TIMEOUT = args_dict.get('retry_delay')
    settings.GET_ENVIRON_STRICT = args_dict.get('strict')
    settings.COUNT_LOG_LINES = args_dict.get('tail_lines')
    settings.CONFIG_FILE = args_dict.get('config') or settings.CONFIG_FILE

    try:
        args.func(args_dict)
    except templating.TemplateRenderingError as e:
        log.error('Template generation error: {}'.format(e))
        sys.exit(1)
    except InvalidYamlError as e:
        log.error('{}'.format(e))
        sys.exit(1)
    except DeprecationError as e:
        log.error('Deprecation warning: {}'.format(e))
        sys.exit(1)
    except RuntimeError as e:
        log.error('RuntimeError: {}'.format(e))
        sys.exit(1)
    except ProvisioningError:
        sys.exit(1)

    print(r'''
                         _(_)_                          wWWWw   _
             @@@@       (_)@(_)   vVVVv     _     @@@@  (___) _(_)_
            @@()@@ wWWWw  (_)\    (___)   _(_)_  @@()@@   Y  (_)@(_)
             @@@@  (___)     `|/    Y    (_)@(_)  @@@@   \|/   (_)
              /      Y       \|    \|/    /(_)    \|      |/      |
           \ |     \ |/       | / \ | /  \|/       |/    \|      \|/
            \|//    \|///    \|//  \|/// \|///    \|//    |//    \|//
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^''')


if __name__ == '__main__':
    main()
