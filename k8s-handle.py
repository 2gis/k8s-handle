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
from config import get_client_config
from k8s.deprecation_checker import ApiDeprecationChecker, DeprecationError
from k8s.resource import Provisioner
from k8s.resource import ProvisioningError

log = logging.getLogger(__name__)
logging.basicConfig(level=settings.LOG_LEVEL, format=settings.LOG_FORMAT, datefmt=settings.LOG_DATE_FORMAT)

parser = argparse.ArgumentParser(description='CLI utility generate k8s resources by templates and apply it to cluster')
subparsers = parser.add_subparsers(dest="command")
subparsers.required = True

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
    args = parser.parse_args()

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

    try:
        context = config.context_load(args.section)
        settings.K8S_NAMESPACE = context.get('k8s_namespace')
        log.info('Using namespace {}'.format(settings.K8S_NAMESPACE))
        renderer = templating.Renderer(settings.TEMPLATES_DIR)
        resources = renderer.generate_by_context(context)

        # INFO rvadim: https://github.com/kubernetes-client/python/issues/430#issuecomment-359483997
        if args.dry_run:
            return

        if 'use_kubeconfig' in args and args.use_kubeconfig:
            load_kube_config()

        else:
            # check that required parameters present
            missing_vars = []

            for key in ['k8s_master_uri', 'k8s_token', 'k8s_ca_base64', 'k8s_namespace']:
                if key in context and context[key] not in ['', None]:
                    continue

                missing_vars.append(key)

            if missing_vars:
                raise RuntimeError(
                    'Variables "{}" not found (or empty) in config file "{}". '
                    'Please, set all required variables: {}.'.format(
                        ', '.join(missing_vars),
                        settings.CONFIG_FILE,
                        ', '.join(['k8s_master_uri', 'k8s_token', 'k8s_ca_base64', 'k8s_namespace'])
                    )
                )

            Configuration.set_default(get_client_config(context))

        deprecation_checker = ApiDeprecationChecker(VersionApi().get_code().git_version[1:])

        for resource in resources:
            deprecation_checker.run(resource)

        provisioner = Provisioner(args.command, args.sync_mode)

        for resource in resources:
            provisioner.run(resource)

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

    print(
        '''
                         _(_)_                          wWWWw   _
             @@@@       (_)@(_)   vVVVv     _     @@@@  (___) _(_)_
            @@()@@ wWWWw  (_)\    (___)   _(_)_  @@()@@   Y  (_)@(_)
             @@@@  (___)     `|/    Y    (_)@(_)  @@@@   \|/   (_)
              /      Y       \|    \|/    /(_)    \|      |/      |
           \ |     \ |/       | / \ | /  \|/       |/    \|      \|/
            \|//    \|///    \|//  \|/// \|///    \|//    |//    \|//
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^'''
    )


if __name__ == '__main__':
    main()
