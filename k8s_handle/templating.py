import os
import glob
import base64
import itertools
import logging
import yaml
from k8s_handle import settings
from hashlib import sha256
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jinja2.exceptions import TemplateNotFound, UndefinedError, TemplateSyntaxError


class TemplateRenderingError(Exception):
    pass


log = logging.getLogger(__name__)


def get_template_contexts(file_path):
    with open(file_path) as f:
        try:
            contexts = yaml.safe_load_all(f.read())
        except Exception as e:
            raise RuntimeError('Unable to load yaml file: {}, {}'.format(file_path, e))

        for context in contexts:
            if context is None:
                continue  # Skip empty YAML documents
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
            yield context


def b64decode(string):
    res = base64.decodebytes(string.encode())
    return res.decode()


def b64encode(string):
    res = base64.b64encode(string.encode())
    return res.decode()


def hash_sha256(string):
    res = sha256()
    res.update(string.encode('utf-8'))
    return res.hexdigest()


def get_env(templates_dir):
    # https://stackoverflow.com/questions/9767585/insert-static-files-literally-into-jinja-templates-without-parsing-them
    def include_file(path):
        path = os.path.join(templates_dir, '../', path)
        output = []
        for file_path in glob.glob(path):
            with open(file_path, 'r') as f:
                output.append(f.read())
        return '\n'.join(output)
    env = Environment(
        undefined=StrictUndefined,
        loader=FileSystemLoader([templates_dir]))

    env.filters['b64decode'] = b64decode
    env.filters['b64encode'] = b64encode
    env.filters['hash_sha256'] = hash_sha256
    env.globals['include_file'] = include_file

    log.debug('Available templates in path {}: {}'.format(templates_dir, env.list_templates()))
    return env


def _create_dir(dir):
    try:
        os.makedirs(dir)
    except os.error as e:
        log.debug(e)
        pass


class Renderer:
    def __init__(self, templates_dir):
        self._templates_dir = templates_dir
        self._env = get_env(self._templates_dir)

    def generate_by_context(self, context):
        if context is None:
            raise RuntimeError('Can\'t generate templates from None context')

        templates = context.get('templates', [])
        if len(templates) == 0:
            templates = context.get('kubectl', [])
            if len(templates) == 0:
                return

        templates = filter(
            lambda i: self._evaluate_tags(self._get_template_tags(i),
                                          settings.ONLY_TAGS,
                                          settings.SKIP_TAGS),
            templates
        )

        output = []
        for template in templates:
            try:
                path = self._generate_file(template, settings.TEMP_DIR, context)
                log.info('File "{}" successfully generated'.format(path))
                output.append(path)
            except TemplateNotFound:
                raise TemplateRenderingError('Template "{}" not found'.format(template))
            except (UndefinedError, TemplateSyntaxError) as e:
                raise TemplateRenderingError('Unable to render {}, due to: {}'.format(template, e))
        return output

    def _get_template_tags(self, template):
        if 'tags' not in template:
            return set(['untagged'])

        tags = template['tags']

        if isinstance(tags, list):
            tags = set([i for i, _ in itertools.groupby(tags)])
        elif isinstance(tags, str):
            tags = set(tags.split(','))
        else:
            raise TypeError('Unable to parse tags of "{}" template: unexpected type {}'.format(template,
                                                                                               type(tags)))

        return tags

    def _evaluate_tags(self, tags, only_tags, skip_tags):
        skip = False

        if only_tags:
            if tags.isdisjoint(only_tags):
                skip = True

        if skip_tags:
            if skip:
                pass  # we decided to skip template already
            elif not tags.isdisjoint(skip_tags):
                skip = True

        return not skip

    def _generate_file(self, item, dir,  context):
        _create_dir(dir)
        try:
            log.info('Trying to generate file from template "{}" in "{}"'.format(item['template'], dir))
            template = self._env.get_template(item['template'])
        except TemplateNotFound as e:
            log.info('Templates path: {}, available templates:{}'.format(self._templates_dir,
                                                                         self._env.list_templates()))
            raise e
        except KeyError:
            raise RuntimeError('Templates section doesn\'t have any template items')
        new_name = item['template'].replace('.j2', '')
        path = os.path.join(dir, new_name)
        if not os.path.exists(os.path.dirname(path)):
            _create_dir(os.path.dirname(path))
        with open(path, 'w+') as f:
            f.write(template.render(context))
        return path
