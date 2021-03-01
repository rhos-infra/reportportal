#!/usr/bin/python


def rp_attributes(attributes_list):
    """Return a list of dictionary elements for ReportPortal v5 attributes

    This filter gets lists of (strings) attributes separated by ':' and convert
    it to a list of dictionary elements suitable for updating attributes of
    launches in ReportPortal v5.

    Input:
        ['K1:V1', 'K2:V2', ...]

    Output:
        [{'key': 'K1', 'value': 'V1'}, {'key': 'K2', 'value': 'V2'}, ... ]
    """
    attributes = []

    for attr in attributes_list:
        key, value = attr.split(':', 1)
        attributes.append({'key': key, 'value': value})

    return attributes


class FilterModule(object):

    def filters(self):
        return {
            'rp_attributes': rp_attributes,
        }
