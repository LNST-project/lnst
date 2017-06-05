"""
This module contains helper functions useful when writing recipes
that use PerfRepo.

Copyright 2015 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import logging
from lnst.Common.Utils import Noop

def netperf_baseline_template(module, baseline, test_type="STREAM"):
    module.unset_option('threshold')
    module.unset_option('threshold_deviation')

    if baseline.get_texec() is None:
        return module

    try:
        if test_type == "RR":
            throughput = baseline.get_value('rr_rate')
            deviation = baseline.get_value('rr_rate_deviation')
        else:
            throughput = baseline.get_value('throughput')
            deviation = baseline.get_value('throughput_deviation')
    except:
        logging.error("Invalid baseline TestExecution passed.")
        return module

    logging.debug("Setting Netperf threshold.")
    if throughput is not None and deviation is not None:
        if test_type == "RR":
            module.update_options({'threshold': '%s Trans/sec' % throughput,
                                   'threshold_deviation': '%s Trans/sec' % deviation})
        else:
            module.update_options({'threshold': '%s bits/sec' % throughput,
                                   'threshold_deviation': '%s bits/sec' % deviation})
    return module

def perfrepo_baseline_to_dict(baseline, test_type="STREAM"):
    if baseline.get_texec() is None:
        return {}

    try:
        if test_type == "RR":
            throughput = baseline.get_value('rr_rate')
            deviation = baseline.get_value('rr_rate_deviation')
        else:
            throughput = baseline.get_value('throughput')
            deviation = baseline.get_value('throughput_deviation')
    except:
        logging.error("Invalid baseline TestExecution passed.")
        return {}

    if throughput is not None and deviation is not None:
        if test_type == "RR":
            return {'threshold': '%s Trans/sec' % throughput,
                    'threshold_deviation': '%s Trans/sec' % deviation}
        else:
            return {'threshold': '%s bits/sec' % throughput,
                    'threshold_deviation': '%s bits/sec' % deviation}
    return {}

def netperf_result_template(perfrepo_result, netperf_result, test_type="STREAM"):
    if isinstance(perfrepo_result, Noop):
        return perfrepo_result

    try:
        result = netperf_result.get_result()
        res_data = result['res_data']
        rate = res_data['rate']
        deviation = res_data['rate_deviation']
    except:
        logging.error("Netperf didn't return usable result data.")
        return perfrepo_result

    logging.debug("Adding Netperf results to PerfRepo object.")
    if test_type == "RR":
        perfrepo_result.add_value('rr_rate', rate)
        perfrepo_result.add_value('rr_rate_min', rate - deviation)
        perfrepo_result.add_value('rr_rate_max', rate + deviation)
        perfrepo_result.add_value('rr_rate_deviation', deviation)
    else:
        perfrepo_result.add_value('throughput', rate)
        perfrepo_result.add_value('throughput_min', rate - deviation)
        perfrepo_result.add_value('throughput_max', rate + deviation)
        perfrepo_result.add_value('throughput_deviation', deviation)

    return perfrepo_result
