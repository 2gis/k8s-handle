import json
import re


def split_str_by_capital_letters(item):
    # upper the first letter
    item = item[0].upper() + item[1:]
    # transform 'Service' to 'service', 'CronJob' to 'cron_job', 'TargetPort' to 'target_port', etc.
    return '_'.join(re.findall(r'[A-Z][^A-Z]*', item)).lower()


def add_indent(json_str):
    try:
        return json.dumps(json.loads(json_str), indent=4)
    except:  # NOQA
        return json_str
