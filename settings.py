import os

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

CONFIG_FILE = os.environ.get('CONFIG_FILE', 'config.yaml')

COMMON_SECTION_NAME = 'common'
TEMPLATES_DIR = os.environ.get('TEMPLATES_DIR', 'templates')

K8S_CA = os.environ.get('K8S_CA')
K8S_HOST = os.environ.get('K8S_HOST')
K8S_TOKEN = os.environ.get('K8S_TOKEN')
K8S_NAMESPACE = os.environ.get('K8S_NAMESPACE')
K8S_CONFIG_DIR = os.environ.get('K8S_CONFIG_DIR', '{}/.kube/'.format(os.path.expanduser('~')))

TEMP_DIR = os.environ.get('TEMP_DIR', '/tmp/k8s-handle')

CHECK_STATUS_TRIES = 360
CHECK_STATUS_TIMEOUT = 5

CHECK_CONTAINERS_IN_POD_TRIES = 360
CHECK_CONTAINERS_IN_POD_TIMEOUT = 5

CHECK_POD_STATUS_TRIES = 360
CHECK_POD_STATUS_TIMEOUT = 5

CHECK_DAEMONSET_STATUS_TRIES = 10
CHECK_DAEMONSET_STATUS_TIMEOUT = 5

GET_ENVIRON_STRICT = False
