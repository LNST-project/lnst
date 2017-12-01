"""
This module defines helper functions for interacting with PerfRepo
that can be imported directly into LNST Python tasks.

Copyright 2016 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jtluka@redhat.com (Jan Tluka)
"""

import os
import re
import logging
import hashlib

from lnst.Common.Path import Path
from lnst.RecipeCommon.PerfRepo.PerfRepoMapping import PerfRepoMapping
from lnst.Common.Utils import dict_to_dot, list_to_dot
from lnst.Common.Utils import Noop
from lnst.Common.LnstError import LnstError

try:
    from perfrepo import PerfRepoRESTAPI
    from perfrepo import PerfRepoTestExecution
    from perfrepo import PerfRepoValue
except:
    PerfRepoRESTAPI = None
    PerfRepoTestExecution = None
    PerfRepoValue = None

class PerfRepoError(LnstError):
    """Exception used by PerfRepo related stuff"""
    pass


def generate_perfrepo_comment(hosts=[], user_comment=None):
    """ Prepare the PerfRepo comment.

    By default it will include kernel versions used on the hosts and
    Beaker job url.

    Keyword arguments:
    hosts -- list of HostAPI objects
    user_comment -- additional user specified comment
    """

    comment = ""

    for host in hosts:
        host_cfg = host.get_configuration()
        comment += "Kernel (%s): %s<BR>" % \
                       (host_cfg['id'], host_cfg['kernel_release'])

    # if we're running in Beaker environment, include job url
    if 'BEAKER' in os.environ and 'JOBID' in os.environ:
        bkr_server = os.environ['BEAKER']
        bkr_jobid = os.environ['JOBID']
        bkr_job_url = bkr_server + 'jobs/' + bkr_jobid
        comment += "Beaker job: %s<BR>" % bkr_job_url

    if user_comment:
        comment += user_comment

    return comment





class PerfRepoAPI(object):
    def __init__(self, mapping_file_path, url=None, username=None, password=None):
        self._mapping_file_path = mapping_file_path
        self._url = url
        self._username = username
        self._password = password

        self._rest_api = None
        self._mapping = None

    def connect_PerfRepo(self, max_retries=3):
        if not self.connected():
            #TODO: store credentials in config or not
            #if self._url is None:
            #    self._url = lnst_config.get_option("perfrepo", "url")
            #if self._username is None:
            #    self._username = lnst_config.get_option("perfrepo", "username")
            #if self._password is None:
            #    self._password = lnst_config.get_option("perfrepo", "password")

            if not self._url:
                logging.warn("No PerfRepo URL specified in config file")
            if not self._username:
                logging.warn("No PerfRepo username specified in config file")
            if not self._password:
                logging.warn("No PerfRepo password specified in config file")
            if self._url and self._username and self._password:
                self.connect(self._url, self._username, self._password, max_retries)

            path = Path(None, self._mapping_file_path)
            self.load_mapping(path)

            if not self.connected():
                if PerfRepoRESTAPI is None:
                    logging.warn("Python PerfRepo library not found.")
                logging.warn("Connection to PerfRepo incomplete, further "\
                             "PerfRepo commands will be ignored.")

    def load_mapping(self, file_path):
        try:
            self._mapping = PerfRepoMapping(file_path.resolve())
        except:
            logging.error("Failed to load PerfRepo mapping file '%s'" %\
                          file_path.abs_path())
            self._mapping = None

    def get_mapping(self):
        return self._mapping

    def connected(self):
        if self._rest_api is not None and self._rest_api.connected() and\
                self._mapping is not None:
            return True
        else:
            return False

    def connect(self, url, username, password, max_retries):
        if PerfRepoRESTAPI is not None:
            self._rest_api = PerfRepoRESTAPI(url, username, password)
            self._rest_api.set_retries(max_retries)
            if not self._rest_api.connected():
                self._rest_api = None
        else:
            self._rest_api = None

    def new_result(self, mapping_key, name, hash_ignore=[]):
        if not self.connected():
            return Noop()

        mapping_id = self._mapping.get_id(mapping_key)
        if mapping_id is None:
            logging.debug("Test key '%s' has no mapping defined!" % mapping_key)
            return Noop()

        logging.debug("Test key '%s' mapped to id '%s'" % (mapping_key,
                                                           mapping_id))

        try:
            test = self._rest_api.test_get_by_id(mapping_id, log=False)
        except Exception as e:
            test = None
            logging.error(str(e))
        if test is None:
            try:
                test = self._rest_api.test_get_by_uid(mapping_id, log=False)
            except Exception as e:
                test = None
                logging.error(str(e))

        if test is not None:
            test_url = self._rest_api.get_obj_url(test)
            logging.debug("Found Test with id='%s' and uid='%s'! %s" % \
                            (test.get_id(), test.get_uid(), test_url))
        else:
            logging.debug("No Test with id or uid '%s' found!" % mapping_id)
            return Noop()

        logging.info("Creating a new result object for PerfRepo")
        result = PerfRepoResult(test, name, hash_ignore)
        return result

    def save_result(self, result):
        if isinstance(result, Noop):
            return
        elif not self.connected():
            raise PerfRepoError("Not connected to PerfRepo.")
        elif isinstance(result, PerfRepoResult):
            if len(result.get_testExecution().get_values()) < 1:
                logging.debug("PerfRepoResult with no result data, skipping "\
                              "send to PerfRepo.")
                return
            h = result.generate_hash()
            logging.debug("Adding hash '%s' as tag to result." % h)
            result.add_tag(h)
            logging.info("Sending TestExecution to PerfRepo.")
            try:
                self._rest_api.testExecution_create(result.get_testExecution())
            except Exception as e:
                logging.error(str(e))
                return

            report_id = self._mapping.get_id(h)
            if not report_id and result.get_testExecution().get_id() is not None:
                logging.debug("No mapping defined for hash '%s'" % h)
                logging.debug("If you want to create a new report and set "\
                              "this result as the baseline run this command:")
                cmd = "perfrepo report create"
                cmd += " name REPORTNAME"

                test = result.get_test()
                cmd += " chart CHARTNAME"
                cmd += " testid %s" % test.get_id()
                series_num = 0
                for m in test.get_metrics():
                    cmd += " series NAME%d" % series_num
                    cmd += " metric %s" % m.get_id()
                    cmd += " tags %s" % h
                    series_num += 1
                cmd += " baseline BASELINENAME"
                cmd += " execid %s" % result.get_testExecution().get_id()
                cmd += " metric %s" % test.get_metrics()[0].get_id()
                logging.debug(cmd)
        else:
            raise PerfRepoError("Parameter result must be an instance "\
                            "of PerfRepoResult")

    def get_baseline(self, report_id):
        if report_id is None or not self.connected():
            return Noop()

        try:
            report = self._rest_api.report_get_by_id(report_id, log=False)
        except Exception as e:
            report = None
            logging.error(str(e))
        if report is None:
            logging.debug("No report with id %s found!" % report_id)
            return Noop()
        logging.debug("Report found: %s" %\
                        self._rest_api.get_obj_url(report))

        baseline = report.get_baseline()

        if baseline is None:
            logging.debug("No baseline set for report %s" %\
                            self._rest_api.get_obj_url(report))
            return Noop()

        baseline_exec_id = baseline["execId"]
        try:
            baseline_testExec = self._rest_api.testExecution_get(baseline_exec_id,
                                                                 log=False)
        except Exception as e:
            baseline_testExec = None
            logging.error(str(e))

        if baseline_testExec is not None:
            logging.debug("TestExecution of baseline: %s" %\
                            self._rest_api.get_obj_url(baseline_testExec))
        else:
            logging.debug("Couldn't get TestExecution of baseline.")
            return Noop()
        return PerfRepoBaseline(baseline_testExec)

    def get_baseline_of_result(self, result):
        if not isinstance(result, PerfRepoResult) or not self.connected():
            return Noop()

        res_hash = result.generate_hash()
        logging.debug("Result hash is: '%s'" % res_hash)

        report_id = self._mapping.get_id(res_hash)
        if report_id is not None:
            logging.debug("Hash '%s' maps to report id '%s'" % (res_hash,
                                                               report_id))
        else:
            logging.debug("Hash '%s' has no mapping defined!" % res_hash)
            return Noop()

        baseline = self.get_baseline(report_id)

        if baseline.get_texec() is None:
            logging.debug("No baseline set for results with hash %s" % res_hash)
        return baseline

    def compare_to_baseline(self, result, report_id, metric_name):
        if not self.connected():
            return False
        baseline_testExec = self.get_baseline(report_id)
        result_testExec = result.get_testExecution()

        return self.compare_testExecutions(result_testExec,
                                           baseline_testExec,
                                           metric_name)

    def compare_testExecutions(self, first, second, metric_name):
        first_value = first.get_value(metric_name)
        first_min = first.get_value(metric_name + "_min")
        first_max = first.get_value(metric_name + "_max")

        second_value = second.get_value(metric_name)
        second_min = second.get_value(metric_name + "_min")
        second_max = second.get_value(metric_name + "_max")

        comp = second_value.get_comparator()
        if comp == "HB":
            if second_min.get_result() > first_max.get_result():
                return False
            return True
        elif comp == "LB":
            if first_min.get_result() > second_max.get_result():
                return False
            return True
        else:
            return False
        return False

class PerfRepoResult(object):
    def __init__(self, test, name, hash_ignore=[]):
        self._test = test
        self._testExecution = PerfRepoTestExecution()
        self._testExecution.set_testId(test.get_id())
        self._testExecution.set_testUid(test.get_uid())
        self._testExecution.set_name(name)
        #self.set_configuration(ctl.get_configuration())
        self._hash_ignore = hash_ignore

    def add_value(self, val_name, value):
        perf_value = PerfRepoValue()
        perf_value.set_metricName(val_name)
        perf_value.set_result(value)

        self._testExecution.add_value(perf_value)

    def set_configuration(self, configuration=None):
        #if configuration is None:
        #    configuration = ctl.get_configuration()
        #for pair in dict_to_dot(configuration, "configuration."):
        #    self._testExecution.add_parameter(pair[0], pair[1])
        pass

    def set_mapping(self, mapping=None):
        #if mapping is None:
        #    mapping = ctl.get_mapping()
        #for pair in list_to_dot(mapping, "mapping.", "machine"):
        #    self._testExecution.add_parameter(pair[0], pair[1])
        pass

    def set_tag(self, tag):
        self._testExecution.add_tag(tag)

    def add_tag(self, tag):
        self.set_tag(tag)

    def set_tags(self, tags):
        for tag in tags:
            self.set_tag(tag)

    def add_tags(self, tags):
        self.set_tags(tags)

    def set_parameter(self, name, value):
        self._testExecution.add_parameter(name, value)

    def set_parameters(self, params):
        for name, value in params:
            self.set_parameter(name, value)

    def set_hash_ignore(self, hash_ignore):
        self._hash_ignore = hash_ignore

    def set_comment(self, comment):
        if comment:
            self._testExecution.set_comment(comment)

    def get_hash_ignore(self):
        return self._hash_ignore

    def get_testExecution(self):
        return self._testExecution

    def get_test(self):
        return self._test

    def generate_hash(self, ignore=[]):
        ignore.extend(self._hash_ignore)
        tags = self._testExecution.get_tags()
        params = self._testExecution.get_parameters()

        sha1 = hashlib.sha1()
        sha1.update(self._testExecution.get_testUid())
        for i in sorted(tags):
            sha1.update(i)
        for i in sorted(params, key=lambda x: x[0]):
            skip = False
            for j in ignore:
                if re.search(j, i[0]):
                    skip = True
                    break
            if skip:
                continue
            sha1.update(i[0])
            sha1.update(str(i[1]))
        return sha1.hexdigest()

class PerfRepoBaseline(object):
    def __init__(self, texec):
        self._texec = texec

    def get_value(self, name):
        if self._texec is None:
            return None
        perfrepovalue = self._texec.get_value(name)
        return perfrepovalue.get_result()

    def get_texec(self):
        return self._texec
