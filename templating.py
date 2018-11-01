import os
import base64
import logging
import yaml
import settings
from hashlib import sha256
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jinja2.exceptions import TemplateNotFound, UndefinedError, TemplateSyntaxError


class TemplateRenderingError(Exception):
    pass


log = logging.getLogger(__name__)


def get_template_contexts(file_path):
    with open(file_path) as f:
        try:
            contexts = yaml.load_all(f.read())
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
    env = Environment(
        undefined=StrictUndefined,
        loader=FileSystemLoader([templates_dir]))
    env.filters['b64decode'] = b64decode
    env.filters['b64encode'] = b64encode
    env.filters['hash_sha256'] = hash_sha256
    log.debug('Available templates in path {}: {}'.format(templates_dir, env.list_templates()))
    return env


def _create_dir(dir):
    try:
        os.makedirs(dir)
    except os.error as e:
        log.debug(e)
        pass


class Renderer:
    def __init__(self, templates_dir=None):
        self._templates_dir = templates_dir
        if self._templates_dir is None:
            self._templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
        self._env = get_env(self._templates_dir)

    def generate_by_context(self, context):
        if context is None:
            raise RuntimeError('Can\'t generate templates from None context')

        templates = context.get('templates', [])
        if len(templates) == 0:
            templates = context.get('kubectl', [])
            if len(templates) == 0:
                return

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
