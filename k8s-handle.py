#!/usr/bin/env python

import argparse
import logging
import sys

from kubernetes.client import Configuration, VersionApi
from kubernetes.config import load_kube_config

import config
import settings
import templating
from config import InvalidYamlException
from config import check_required_vars
from config import get_client_config
from k8s.deprecation_checker import ApiDeprecationChecker, DeprecationError
from k8s.resource import Provisioner
from k8s.resource import ProvisioningError

log = logging.getLogger(__name__)
logging.basicConfig(level=settings.LOG_LEVEL, format=settings.LOG_FORMAT, datefmt=settings.LOG_DATE_FORMAT)

parser = argparse.ArgumentParser(description='CLI utility generate k8s resources by templates and apply it to cluster')
subparsers = parser.add_subparsers()

deploy_parser = subparsers.add_parser('deploy', help='Sub command for deploy')
deploy_parser.add_argument('-s', '--section', required=True, type=str, help='Section to deploy from config file')
deploy_parser.add_argument('-c', '--config', required=False, help='Config file, default: config.yaml')
deploy_parser.add_argument('--dry-run', required=False, action='store_true', help='Don\'t run kubectl commands')
deploy_parser.add_argument('--sync-mode', action='store_true', required=False, default=False,
                           help='Turn on sync mode and wait deployment ending')
deploy_parser.add_argument('--tries', type=int, required=False, default=360,
                           help='Count of tries to check deployment status')
deploy_parser.add_argument('--retry-delay', type=int, required=False, default=5, help='Sleep between tries in seconds')
deploy_parser.add_argument('--strict', action='store_true', required=False,
                           help='Check existence of all env variables in config.yaml and stop deploy if var is not set')
deploy_parser.add_argument('--use-kubeconfig', action='store_true', required=False, help='Try to use kube config')

destroy_parser = subparsers.add_parser('destroy', help='Sub command for destroy app')
destroy_parser.add_argument('-s', '--section', required=True, type=str, help='Section to destroy from config file')
destroy_parser.add_argument('-c', '--config', type=str, required=False, help='Config file, default: config.yaml')
destroy_parser.add_argument('--dry-run', action='store_true', required=False, default=False,
                            help='Don\'t run kubectl commands')
destroy_parser.add_argument('--sync-mode', action='store_true', required=False, default=False,
                            help='Turn on sync mode and wait destruction ending')
destroy_parser.add_argument('--tries', type=int, required=False, default=360,
                            help='Count of tries to check destruction status')
destroy_parser.add_argument('--retry-delay', type=int, required=False, default=5, help='Sleep between tries in seconds')
destroy_parser.add_argument('--use-kubeconfig', action='store_true', required=False, help='Try to use kube config')


def main():
    args = parser.parse_known_args()[0]

    if 'config' in args and args.config:
        settings.CONFIG_FILE = args.config

    if 'tries' in args:
        settings.CHECK_STATUS_TRIES = args.tries
        settings.CHECK_DAEMONSET_STATUS_TRIES = args.tries

    if 'retry_delay' in args:
        settings.CHECK_STATUS_TIMEOUT = args.retry_delay
        settings.CHECK_DAEMONSET_STATUS_TIMEOUT = args.retry_delay

    if 'strict' in args:
        settings.GET_ENVIRON_STRICT = args.strict

    if 'command' not in args:
        parser.print_help()
        sys.exit(1)

    try:
        context = config.load_context_section(args.section)
        log.info('Using default namespace {}'.format(context.get('k8s_namespace')))
        render = templating.Renderer(settings.TEMPLATES_DIR)
        resources = render.generate_by_context(context)
        # INFO rvadim: https://github.com/kubernetes-client/python/issues/430#issuecomment-359483997

        if args.dry_run:
            return

        if 'use_kubeconfig' in args and args.use_kubeconfig:
            load_kube_config()
        else:
            Configuration.set_default(get_client_config(context))
            check_required_vars(context, ['k8s_master_uri', 'k8s_token', 'k8s_ca_base64', 'k8s_namespace'])

        p = Provisioner(args.command, args.sync_mode)
        d = ApiDeprecationChecker(VersionApi().get_code().git_version[1:])

        for resource in resources:
            d.run(resource)
            p.run(resource)

    except templating.TemplateRenderingError as e:
        log.error('Template generation error: {}'.format(e))
        sys.exit(1)
    except InvalidYamlException as e:
        log.error('Incorrect config.yaml: {}'.format(e))
        sys.exit(1)
    except DeprecationError as e:
        log.error('Deprecation warning: {}'.format(e))
        sys.exit(1)
    except RuntimeError as e:
        log.error('RuntimeError: {}'.format(e))
        sys.exit(1)
    except ProvisioningError:
        sys.exit(1)

    print('''
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
