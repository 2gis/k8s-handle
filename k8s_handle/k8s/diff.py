import sys
import logging
import copy
from difflib import ndiff
from datetime import datetime
from functools import reduce
import operator
import yaml
from .adapters import Adapter
from k8s_handle.templating import get_template_contexts
log = logging.getLogger(__name__)

IGNORE_FIELDS = [
    'metadata.annotations:kubectl.kubernetes.io/last-applied-configuration',
    'metadata.annotations:deployment.kubernetes.io/revision',
    'metadata:creationTimestamp',
    'metadata:resourceVersion',
    'metadata:selfLink',
    'metadata:uid',
    'metadata:namespace',
    'metadata:generation',
    'metadata:managedFields',
    'status'
]


def remove_from_dict(d, path, key):
    del reduce(operator.getitem, path, d)[key]


def to_dict(obj):
    if hasattr(obj, 'attribute_map'):
        result = {}
        for k, v in getattr(obj, 'attribute_map').items():
            val = getattr(obj, k)
            if val is not None:
                result[v] = to_dict(val)
        return result
    elif isinstance(obj, list):
        return [to_dict(x) for x in obj]
    elif isinstance(obj, datetime):
        return str(obj)
    elif isinstance(obj, dict):
        newobj = copy.deepcopy(obj)
        for k, v in obj.items():
            newobj[k] = to_dict(obj[k])
        return newobj
    else:
        return obj


def apply_filter(d, field_path):
    try:
        path, field = field_path.split(':')
        path = path.split('.')
    except ValueError:
        del d[field_path]
    else:
        remove_from_dict(d, path, field)


class Diff:
    @staticmethod
    def run(file_path):
        for template_body in get_template_contexts(file_path):
            if template_body.get('kind') == 'Secret':
                log.info(f'Skipping secret {template_body.get("metadata", {}).get("name")}')
                continue
            kube_client = Adapter.get_instance(template_body)
            new = yaml.safe_dump(template_body)
            k8s_object = kube_client.get()
            if k8s_object is None:
                current_dict = {}
            else:
                current_dict = to_dict(k8s_object)
            for field_path in IGNORE_FIELDS:
                try:
                    apply_filter(current_dict, field_path)
                except KeyError:
                    pass
            metadata = current_dict.get('metadata', {})
            if 'annotations' in metadata and metadata['annotations'] == {}:
                del metadata['annotations']
            current = yaml.safe_dump(current_dict)
            if new == current:
                log.info(f' Kind: "{template_body.get("kind")}", '
                         f'name: "{template_body.get("metadata", {}).get("name")}" : NO CHANGES')
            else:
                diff = ndiff(current.splitlines(keepends=True), new.splitlines(keepends=True))
                log.info(f' Kind: "{template_body.get("kind")}", '
                         f'name: "{template_body.get("metadata", {}).get("name")}"')
                sys.stdout.write(''.join(diff))
