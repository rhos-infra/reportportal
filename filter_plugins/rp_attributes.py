#!/usr/bin/python


def rp_attributes(
        attributes_list, value_default='NA', key_len=128, value_len=128):
    """Return a list of dictionary elements for ReportPortal v5 attributes

    This filter gets lists of (strings) attributes separated by ':' and convert
    it to a list of dictionary elements suitable for updating attributes of
    launches in ReportPortal v5.

    Input:
        ['K1:V1', 'K2:V2', ...]

    Output:
        [{'key': 'K1', 'value': 'V1'}, {'key': 'K2', 'value': 'V2'}, ... ]

    :param attributes_list: List of attributes that should be splitted
    :param value_default: The default value to use if a value isn't given
    :param key_len: Key max length
    :param value_len: Value max len
    """
    attributes = []

    for attr in attributes_list:

        attr = attr.replace('\n', ' ').replace('\\n', ' ').strip()

        if ':' not in attr:
            attr += ':'

        key, value = attr.split(':', 1)

        if value is '':
            value = value_default

        if len(key) > key_len:
            key = key[:key_len - 4] + '...'
        if len(value) > value_len:
            value = value[:value_len - 4] + '...'

        attributes.append({'key': key, 'value': value})

    return attributes


class FilterModule(object):

    def filters(self):
        return {
            'rp_attributes': rp_attributes,
        }
