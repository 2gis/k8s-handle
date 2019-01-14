import copy


def merge(dict_x, dict_y):
    result = copy.deepcopy(dict_x)
    for key, value in dict_y.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
            continue

        result[key] = value

    return result
