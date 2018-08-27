import atexit
import logging
import os
import tempfile

import yaml

log = logging.getLogger(__name__)


def file_write_temporary(data):
    def _file_remove(path):
        try:
            os.remove(path)
        except Exception as e:
            log.warning('Unable to remove "{}", due to "{}"'.format(path, e))

    file_ = tempfile.NamedTemporaryFile(delete=False)
    file_.write(data)
    file_.flush()
    atexit.register(_file_remove, file_.name)
    return file_.name


def file_load_yaml(path):
    with open(path) as f:
        return yaml.load(f.read())
