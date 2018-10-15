import os

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s %(levelname)s:%(name)s:%(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

CONFIG_FILE = os.environ.get('CONFIG_FILE', 'config.yaml')

COMMON_SECTION_NAME = 'common'
TEMPLATES_DIR = os.environ.get('TEMPLATES_DIR', 'templates')

K8S_CONFIG_DIR = os.environ.get('K8S_CONFIG_DIR', '{}/.kube/'.format(os.path.expanduser('~')))

K8S_NAMESPACE = None

TEMP_DIR = os.environ.get('TEMP_DIR', '/tmp/k8s-handle')

CHECK_STATUS_TRIES = 360
CHECK_STATUS_TIMEOUT = 5

CHECK_CONTAINERS_IN_POD_TRIES = 360
CHECK_CONTAINERS_IN_POD_TIMEOUT = 5

CHECK_POD_STATUS_TRIES = 360
CHECK_POD_STATUS_TIMEOUT = 5

CHECK_DAEMONSET_STATUS_TRIES = 10
CHECK_DAEMONSET_STATUS_TIMEOUT = 5

COUNT_LOG_LINES = None

GET_ENVIRON_STRICT = False
