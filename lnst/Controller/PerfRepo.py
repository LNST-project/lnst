"""
This module contains the API for PerfRepo.

Copyright 2015 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import requests
import datetime
import re
import logging
import xml.dom.minidom
import textwrap
import pprint
from types import StringType, NoneType
from xml.etree import ElementTree
from xml.etree.ElementTree import Element
from lnst.Common.Utils import recursive_dict_update
from lnst.Common.Utils import dot_to_dict, dict_to_dot, indent

class PerfRepoException(Exception):
    pass

class PerfRepoObject(object):
    def __init__(self):
        pass

    def get_obj_url(self):
        return "/"

    def _set_element_atrib(self, element, name, value):
        if value != None:
            element.set(name, value)

    def to_xml(self):
        pass

    def to_xml_string(self):
        root = self.to_xml()
        return ElementTree.tostring(root)

    def to_pretty_xml_string(self):
        tmp_xml = xml.dom.minidom.parseString(self.to_xml_string())
        return tmp_xml.toprettyxml()

    def __str__(self):
        return self.to_pretty_xml_string()

class PerfRepoTest(PerfRepoObject):
    def __init__(self, xml=None):
        if type(xml) is NoneType:
            self._id = None
            self._name = None
            self._uid = None
            self._description = None
            self._groupid = None
            self._metrics = []
        elif type(xml) is StringType or isinstance(xml, Element):
            if type(xml) is StringType:
                root = ElementTree.fromstring(xml)
            else:
                root = xml
            if root.tag != "test":
                raise PerfRepoException("Invalid xml.")

            self._id = root.get("id")
            self._name = root.get("name")
            self._uid = root.get("uid")
            self._groupid = root.get("groupId")
            self._description = root.find("description").text
            self._metrics = []
            for metric in root.find("metrics"):
                if metric.tag != "metric":
                    continue
                self._metrics.append(PerfRepoMetric(metric))
        else:
            raise PerfRepoException("Parameter xml must be"\
                                    " a string, an Element or None")

    def get_obj_url(self):
        return "/test/%s" % self._id

    def get_id(self):
        return self._id

    def get_name(self):
        return self._name

    def get_uid(self):
        return self._uid

    def get_description(self):
        return self._description

    def get_groupid(self):
        return self._groupid

    def get_metrics(self):
        return self._metrics

    def set_id(self, id):
        self._id = id

    def set_name(self, name):
        self._name = name

    def set_uid(self, uid):
        self._uid = uid

    def set_description(self, description):
        self._description = description

    def set_groupid(self, groupid):
        self._groupid = groupid

    def add_metric(self, metric):
        if not isinstance(metric, PerfRepoMetric):
            return None
        else:
            self._metrics.append(metric)
            return metric

    def to_xml(self):
        root = Element('test')
        self._set_element_atrib(root, 'id', self._id)
        self._set_element_atrib(root, 'name', self._name)
        self._set_element_atrib(root, 'uid', self._uid)
        self._set_element_atrib(root, 'groupId', self._groupid)
        description = ElementTree.SubElement(root, 'description')
        description.text = self._description
        metrics = ElementTree.SubElement(root, 'metrics')
        for metric in self._metrics:
            metrics.append(metric.to_xml())

        return root

    def __str__(self):
        ret_str = """\
                  id = %s
                  uid = %s
                  name = %s
                  groupid = %s
                  description:
                  """ % ( self._id,
                          self._uid,
                          self._name,
                          self._groupid)
        ret_str = textwrap.dedent(ret_str)
        ret_str += indent(self._description, 4)
        ret_str += "metrics:\n"
        for metric in self._metrics:
            ret_str +=  indent(str(metric), 4)
            ret_str +=  indent("------------------------", 4)
        return textwrap.dedent(ret_str)

class PerfRepoTestExecution(PerfRepoObject):
    def __init__(self, xml=None):
        if type(xml) is NoneType:
            self._id = None
            self._name = None
            self._started = datetime.datetime.utcnow().isoformat()
            self._testId = None
            self._testUid = None
            self._comment = ""

            self._values = []
            self._tags = []
            self._parameters = []
        elif type(xml) is StringType or isinstance(xml, Element):
            if type(xml) is StringType:
                root = ElementTree.fromstring(xml)
            else:
                root = xml
            if root.tag != "testExecution":
                raise PerfRepoException("Invalid xml.")

            self._id = root.get("id")
            self._name = root.get("name")
            self._started = root.get("started")
            self._testId = root.get("testId")
            self._testUid = root.get("testUid")
            self._comment = root.find("comment").text

            self._values = []
            for value in root.find("values"):
                if value.tag != "value":
                    continue
                self._values.append(PerfRepoValue(value))

            self._tags = []
            for tag in root.find("tags"):
                if tag.tag != "tag":
                    continue
                self._tags.append(tag.get("name"))

            self._parameters = []
            for param in root.find("parameters"):
                if param.tag != "parameter":
                    continue
                self._parameters.append((param.get("name"), param.get("value")))
        else:
            raise PerfRepoException("Parameter xml must be"\
                                    " a string, an Element or None")

    def get_obj_url(self):
        return "/exec/%s" % self._id

    def set_id(self, id):
        self._id = id

    def get_id(self):
        return self._id

    def set_name(self, name):
        self._name = name

    def get_name(self):
        return self._name

    def set_started(self, date=None):
        if isinstance(date, NoneType):
            self._started = datetime.datetime.utcnow().isoformat()
        else:
            self._started = date

    def get_started(self):
        return self._started

    def set_testId(self, testId):
        if isinstance(testId, PerfRepoTest):
            self._testId = testId.get_id()
        else:
            self._testId = testId

    def get_testId(self):
        return self._testId

    def set_testUid(self, testUid):
        if isinstance(testUid, PerfRepoTest):
            self._testUid = testUid.get_uid()
        else:
            self._testUid = testUid

    def get_testUid(self):
        return self._testUid

    def set_comment(self, comment):
        self._comment = comment

    def get_comment(self):
        return self._comment

    def add_value(self, value):
        self._values.append(value)

    def get_values(self):
        return self._values

    def get_value(self, metric_name):
        for val in self._values:
            if val.get_metricName() == metric_name:
                return val

    def add_tag(self, tag):
        if tag is None:
            return
        self._tags.append(str(tag))

    def get_tags(self):
        return self._tags

    def add_parameter(self, name, value):
        self._parameters.append((name, value))

    def get_parameters(self):
        return self._parameters

    def to_xml(self):
        root = Element('testExecution')
        self._set_element_atrib(root, 'id', self._id)
        self._set_element_atrib(root, 'name', self._name)
        self._set_element_atrib(root, 'started', self._started)
        self._set_element_atrib(root, 'testId', self._testId)
        self._set_element_atrib(root, 'testUid', self._testUid)
        comment = ElementTree.SubElement(root, 'comment')
        comment.text = self._comment

        parameters = ElementTree.SubElement(root, 'parameters')
        for param in self._parameters:
            param_elem = ElementTree.SubElement(parameters, 'parameter')
            self._set_element_atrib(param_elem, "name", param[0])
            self._set_element_atrib(param_elem, "value", param[1])

        tags = ElementTree.SubElement(root, 'tags')
        for tag in self._tags:
            tag_elem = ElementTree.SubElement(tags, 'tag')
            self._set_element_atrib(tag_elem, "name", tag)

        values = ElementTree.SubElement(root, 'values')
        for value in self._values:
            values.append(value.to_xml())

        return root

    def __str__(self):
        ret_str = """\
                  id = %s
                  name = %s
                  date = %s
                  testId = %s
                  testUid = %s
                  comment = %s
                  tags = %s
                  """ % ( self._id,
                          self._name,
                          self._started,
                          self._testId,
                          self._testUid,
                          self._comment,
                          " ".join(self._tags))
        ret_str = textwrap.dedent(ret_str)
        ret_str += "parameters:\n"
        for param in self._parameters:
            ret_str +=  indent("%s = %s" % (param[0], param[1]), 4)
        ret_str += "values:\n"
        for val in self._values:
            ret_str +=  indent(str(val), 4)
            ret_str +=  indent("------------------------", 4)
        return textwrap.dedent(ret_str)

class PerfRepoValue(PerfRepoObject):
    def __init__(self, xml=None):
        if type(xml) is NoneType:
            self._metricComparator = None
            self._metricName = None
            self._result = None
            self._parameters = []
        elif type(xml) is StringType or isinstance(xml, Element):
            if type(xml) is StringType:
                root = ElementTree.fromstring(xml)
            else:
                root = xml
            if root.tag != "value":
                raise PerfRepoException("Invalid xml.")

            self._metricComparator = root.get("metricComparator")
            self._metricName = root.get("metricName")
            self._result = float(root.get("result"))

            self._parameters = []
            for param in root.find("parameters"):
                if param.tag != "parameter":
                    continue
                self._parameters.append((param.get("name"), param.get("value")))
        else:
            raise PerfRepoException("Parameter xml must be"\
                                    " a string, an Element or None")

    def set_result(self, result):
        self._result = result

    def set_comparator(self, comparator):
        if comparator not in ["HB", "LB"]:
            raise PerfRepoException("Comparator must be HB/LB.")
        self._metricComparator = comparator

    def set_metricName(self, name):
        self._metricName = name

    def add_parameter(self, name, value):
        self._parameters.append((name, value))

    def get_parameters(self):
        return self._parameters

    def get_metricName(self):
        return self._metricName

    def get_comparator(self):
        return self._metricComparator

    def get_result(self):
        return self._result

    def to_xml(self):
        root = Element('value')
        self._set_element_atrib(root, 'metricComparator',
                                      self._metricComparator)
        self._set_element_atrib(root, 'metricName', self._metricName)
        self._set_element_atrib(root, 'result', str(self._result))

        parameters = ElementTree.SubElement(root, 'parameters')
        for param in self._parameters:
            param_elem = ElementTree.SubElement(parameters, 'parameter')
            self._set_element_atrib(param_elem, "name", param[0])
            self._set_element_atrib(param_elem, "value", param[1])
        return root

    def __str__(self):
        ret_str = """\
                  metric name = %s
                  result = %s
                  """ % ( self._metricName,
                          self._result)
        ret_str = textwrap.dedent(ret_str)
        ret_str += "parameters:\n"
        for param in self._parameters:
            ret_str +=  indent("%s = %s" % (param[0], param[1]), 4)
        return textwrap.dedent(ret_str)

class PerfRepoMetric(PerfRepoObject):
    def __init__(self, xml=None):
        if type(xml) is NoneType:
            self._id = None
            self._name = None
            self._description = None
            self._comparator = None
        elif type(xml) is StringType or isinstance(xml, Element):
            if type(xml) is StringType:
                root = ElementTree.fromstring(xml)
            else:
                root = xml
            if root.tag != "metric":
                raise PerfRepoException("Invalid xml.")

            self._id = root.get("id")
            self._name = root.get("name")
            self._comparator = root.get("comparator")
            self._description = root.find("description").text
        else:
            raise PerfRepoException("Parameter xml must be"\
                                    " a string, an Element or None")

    def get_id(self):
        return self._id

    def get_name(self):
        return self._id

    def get_description(self):
        return self._description

    def get_comparator(self):
        return self._comparator

    def set_id(self, id):
        self._id = id

    def set_name(self, name):
        self._name = name

    def set_description(self, description):
        self._description = description

    def set_comparator(self, comparator):
        if comparator not in ["HB", "LB"]:
            raise PerfRepoException("Invalid comparator value.")
        self._comparator = comparator

    def to_xml(self):
        root = Element('metric')
        self._set_element_atrib(root, 'id', self._id)
        self._set_element_atrib(root, 'name', self._name)
        description = ElementTree.SubElement(root, 'description')
        description.text = self._description
        self._set_element_atrib(root, 'comparator', self._comparator)

        return root

    def __str__(self):
        ret_str = """\
                  id = %s
                  name = %s
                  comparator = %s
                  description:
                  """ % ( self._id,
                          self._name,
                          self._comparator)
        ret_str = textwrap.dedent(ret_str)
        ret_str += indent(self._description, 4)
        return ret_str

class PerfRepoReport(PerfRepoObject):
    def __init__(self, xml=None):
        self._user = None
        if type(xml) is NoneType:
            self._id = None
            self._name = None
            self._type = None
            self._properties = {}
        elif type(xml) is StringType or isinstance(xml, Element):
            if type(xml) is StringType:
                root = ElementTree.fromstring(xml)
            else:
                root = xml
            if root.tag != "report":
                raise PerfRepoException("Invalid xml.")

            self._id = root.get("id")
            self._name = root.get("name")
            self._type = root.get("type")
            self._properties = {}
            for entry in root.find("properties"):
                if entry.tag != "entry":
                    continue
                key_tag = entry.find("key")
                value_tag = entry.find("value")
                tmp_dict = dot_to_dict(value_tag.get("name"),
                                       value_tag.get("value"))
                recursive_dict_update(self._properties, tmp_dict)
        else:
            raise PerfRepoException("Parameter xml must be"\
                                    " a string, an Element or None")

    def get_obj_url(self):
        return "/reports/%s/%s" % (self._type.lower(), self._id)

    def _find_max_num(self, str_tmp, search_dict):
        max_num = -1
        for key, item in search_dict.items():
            match = re.match(r'%s(\d)+' % str_tmp, key)
            if match == None:
                continue
            num = int(match.group(1))

            if num > max_num:
                max_num = num
        return max_num

    def get_chart(self, chart_num):
        chart_name = "chart%d" % chart_num
        for key, chart in self._properties.items():
            if key == chart_name:
                return chart
        return None

    def add_chart(self, name, test_id):
        max_chart_num = self._find_max_num("chart", self._properties)

        chart_name = "chart%d" % (max_chart_num + 1)

        new_chart = self._properties[chart_name] = {}
        new_chart["name"] = str(name)
        new_chart["test"] = str(test_id)

        return new_chart

    def del_chart(self, chart_num):
        chart_name = "chart%d" % chart_num

        if chart_name in self._properties:
            chart = self._properties[chart_name]
            del self._properties[chart_name]
            return chart
        else:
            return None

    def set_chart_name(self, chart_num, name):
        chart = self.get_chart(chart_num)

        if chart:
            chart["name"] = name
            return chart
        else:
            return None

    def set_chart_test_id(self, chart_num, test_id):
        chart = self.get_chart(chart_num)

        if chart:
            chart["test"] = test_id
            return chart
        else:
            return None

    def get_baseline(self, chart_num=0, index=-1):
        chart = self.get_chart(chart_num)

        if chart is None:
            return None

        if index >= 0:
            baseline_name = "baseline%d" % (index)
            for key, item in chart.items():
                if key == baseline_name:
                    return item
            return None
        else:
            baselines = []
            for key, item in chart.items():
                if re.match(r'baseline\d+', key):
                    baselines.append(item)
            if abs(index) <= len(baselines):
                return baselines[index]
            else:
                return None

    def add_baseline(self, chart_num, name, exec_id, metric_id):
        if chart_num is None:
            chart_num = self._find_max_num("chart", self._properties)

        chart = self.get_chart(chart_num)
        if chart is None:
            return None

        max_baseline_num = self._find_max_num("baseline", chart)

        baseline_name = "baseline%d" % (max_baseline_num + 1)

        new_baseline = chart[baseline_name] = {}
        new_baseline["name"] = str(name)
        new_baseline["metric"] = str(metric_id)
        new_baseline["execId"] = str(exec_id)

        return new_baseline

    def del_baseline(self, chart_num, baseline_num):
        chart = self.get_chart(chart_num)
        if chart is None:
            return None

        baseline_name = "baseline%d" % (baseline_num)

        if baseline_name in chart:
            baseline = chart[baseline_name]
            del chart[baseline_name]
            return baseline
        else:
            return None

    def set_baseline_name(self, chart_num, baseline_num, name):
        baseline = self.get_baseline(chart_num, baseline_num)

        if baseline is None:
            return None

        baseline["name"] = name
        return baseline

    def set_baseline_metric(self, chart_num, baseline_num, metric_id):
        baseline = self.get_baseline(chart_num, baseline_num)

        if baseline is None:
            return None

        baseline["metric"] = metric_id
        return baseline

    def set_baseline_execid(self, chart_num, baseline_num, exec_id):
        baseline = self.get_baseline(chart_num, baseline_num)

        if baseline is None:
            return None

        baseline["execId"] = exec_id
        return baseline

    def add_series(self, chart_num, name, metric_id, tags=[]):
        if chart_num is None:
            chart_num = self._find_max_num("chart", self._properties)

        chart = self.get_chart(chart_num)
        if chart is None:
            return None

        max_series_num = self._find_max_num("series", chart)

        series_name = "series%d" % (max_series_num + 1)

        new_series = chart[series_name] = {}
        new_series["name"] = name
        new_series["metric"] = metric_id
        new_series["tags"] = " ".join(tags)

        return new_series

    def get_series(self, chart_num, series_num):
        chart = self.get_chart(chart_num)
        if chart is None:
            return None

        series_name = "series%d" % int(series_num)
        for key, item in chart.items():
            if key == series_name:
                return item
        return None

    def del_series(self, chart_num, series_num):
        if chart_num is None:
            chart_num = self._find_max_num("chart", self._properties)

        chart = self.get_chart(chart_num)
        if chart is None:
            return None

        series_name = "series%d" % (series_num)

        if series_name in chart:
            series = chart[series_name]
            del chart[series_name]
            return series
        else:
            return None

    def set_series_name(self, chart_num, series_num, name):
        series = self.get_series(chart_num, series_num)

        if series is None:
            return None

        series["name"] = name
        return series

    def set_series_metric(self, chart_num, series_num, metric_id):
        series = self.get_series(chart_num, series_num)

        if series is None:
            return None

        series["metric"] = metric_id
        return series

    def set_series_tags(self, chart_num, series_num, tags):
        series = self.get_series(chart_num, series_num)

        if series is None:
            return None

        series["tags"] = " ".join(tags)
        return series

    def remove_series_tags(self, chart_num, series_num, remove_tags):
        series = self.get_series(chart_num, series_num)

        if series is None:
            return None

        tags = series["tags"].split(" ")

        for tag in remove_tags:
            for i in range(tags.count(tag)):
                tags.remove(tag)

        series["tags"] = " ".join(tags)
        return series

    def add_series_tags(self, chart_num, series_num, add_tags):
        series = self.get_series(chart_num, series_num)

        if series is None:
            return None

        tags = series["tags"].split(" ")

        for tag in add_tags:
            if tags.count(tag) == 0:
                tags.append(tag)

        series["tags"] = " ".join(tags)
        return series

    def set_id(self, new_id=None):
        self._id = new_id

    def get_id(self):
        return self._id

    def set_name(self, new_name=None):
        self._name = new_name

    def get_name(self):
        return self._name

    def set_type(self, new_type=None):
        self._type = new_type

    def get_type(self):
        return self._type

    def set_user(self, new_user=None):
        self._user = new_user

    def get_user(self):
        return self._user

    def to_xml(self):
        root = Element('report')
        self._set_element_atrib(root, 'id', self._id)
        self._set_element_atrib(root, 'name', self._name)
        self._set_element_atrib(root, 'type', self._type)
        self._set_element_atrib(root, 'user', self._user)

        properties = ElementTree.SubElement(root, 'properties')
        dot_props = dict_to_dot(self._properties)
        for prop in dot_props:
            entry_elem = ElementTree.SubElement(properties, 'entry')
            key_elem = ElementTree.SubElement(entry_elem, 'key')
            value_elem = ElementTree.SubElement(entry_elem, 'value')

            key_elem.text = prop[0]
            self._set_element_atrib(value_elem, 'name', prop[0])
            self._set_element_atrib(value_elem, 'value', prop[1])

        return root

    def __str__(self):
        str_props = pprint.pformat(self._properties)
        ret_str = """\
                  id = %s
                  name = %s
                  type = %s
                  properties =
                  """ % ( self._id,
                          self._name,
                          self._type)
        ret_str = textwrap.dedent(ret_str)
        ret_str += str_props
        return textwrap.dedent(ret_str)

class PerfRepoRESTAPI(object):
    '''Wrapper class for the REST API provided by PerfRepo'''
    def __init__(self, url, user, password):
        self._url = url
        self._user = user
        self._password = password

        self._session = requests.Session()
        self._session.auth = (self._user, self._password)
        self._session.stream = True
        self._session.headers['Content-Type'] = 'text/xml'
        logging.getLogger("requests").setLevel(logging.WARNING)

    def get_obj_url(self, obj):
        if not isinstance(obj, PerfRepoObject):
            return ""
        return self._url + obj.get_obj_url()

    def test_get_by_id(self, test_id, log=True):
        get_url = self._url + '/rest/test/id/%s' % test_id
        response = self._session.get(get_url)
        if response.status_code != 200:
            if log:
                logging.debug(response.text)
            return None
        else:
            if log:
                logging.debug("GET %s success" % get_url)
            return PerfRepoTest(response.content)

    def test_get_by_uid(self, test_uid, log=True):
        get_url = self._url + '/rest/test/uid/%s' % test_uid
        response = self._session.get(get_url)
        if response.status_code != 200:
            if log:
                logging.debug(response.text)
            return None
        else:
            if log:
                logging.debug("GET %s success" % get_url)
            return PerfRepoTest(response.content)

    def test_create(self, test, log=True):
        post_url = self._url + '/rest/test/create'
        response = self._session.post(post_url, data=test.to_xml_string())
        if response.status_code != 201:
            if log:
                logging.debug(response.text)
            return None
        else:
            new_id = response.headers["Location"].split('/')[-1]
            test.set_id(new_id)
            if log:
                logging.debug("POST %s success" % post_url)
                logging.info("Obj url: %s" % self.get_obj_url(test))
            return test

    def test_add_metric(self, test_id, metric, log=True):
        post_url = self._url + '/rest/test/id/%s/addMetric' % test_id
        response = self._session.post(post_url, data=metric.to_xml_string)
        if response.status_code != 201:
            if log:
                logging.debug(response.text)
            return None
        else:
            new_id = response.headers["Location"].split('/')[-1]
            metric.set_id(new_id)
            if log:
                logging.debug("POST %s success" % post_url)
                logging.info("Obj url: %s" % self.get_obj_url(test))
            return metric

    def test_delete(self, test_id, log=True):
        delete_url = self._url + '/rest/test/id/%s' % test_id
        response = self._session.delete(delete_url)
        if response.status_code != 204:
            return False
        else:
            if log:
                logging.debug("DELETE %s success" % delete_url)
            return True

    def metric_get(self, metric_id, log=True):
        get_url = self._url + '/rest/metric/%s' % metric_id
        response = self._session.get(get_url)
        if response.status_code != 200:
            if log:
                logging.debug(response.text)
            return None
        else:
            if log:
                logging.debug("GET %s success" % get_url)
            return PerfRepoMetric(response.content)

    def testExecution_get(self, testExec_id, log=True):
        get_url = self._url + '/rest/testExecution/%s' % testExec_id
        response = self._session.get(get_url)
        if response.status_code != 200:
            if log:
                logging.debug(response.text)
            return None
        else:
            if log:
                logging.debug("GET %s success" % get_url)
            return PerfRepoTestExecution(response.content)

    def testExecution_create(self, testExec, log=True):
        post_url = self._url + '/rest/testExecution/create'
        response = self._session.post(post_url, data=testExec.to_xml_string())
        if response.status_code != 201:
            if log:
                logging.debug(response.text)
            return None
        else:
            new_id = response.headers["Location"].split('/')[-1]
            testExec.set_id(new_id)
            if log:
                logging.debug("POST %s success" % post_url)
                logging.info("Obj url: %s" % self.get_obj_url(testExec))
            return testExec

    def testExecution_delete(self, testExec_id, log=True):
        delete_url = self._url + '/rest/testExecution/%s' % testExec_id
        response = self._session.delete(delete_url)
        if response.status_code != 204:
            if log:
                logging.debug(response.text)
            return False
        else:
            if log:
                logging.debug("DELETE %s success" % delete_url)
            return True

    def testExecution_add_value(self, value, log=True):
        post_url = self._url + '/rest/testExecution/addValue'
        #TODO
        return self._session.post(post_url, data=value)

    def testExecution_get_attachment(self, attachment_id, log=True):
        get_url = self._url + '/rest/testExecution/attachment/%s' % \
                                                                attachment_id
        #TODO
        return self._session.get(get_url)

    def testExecution_add_attachment(self, testExec_id, attachment, log=True):
        post_url = self._url + '/rest/testExecution/%s/addAttachment' % \
                                                                testExec_id
        #TODO
        return self._session.post(post_url, data=attachment)

    def report_get_by_id(self, report_id, log=True):
        get_url = self._url + '/rest/report/id/%s' % report_id
        response = self._session.get(get_url)
        if response.status_code != 200:
            if log:
                logging.debug(response.text)
            return None
        else:
            if log:
                logging.debug("GET %s success" % get_url)
            return PerfRepoReport(response.content)

    def report_create(self, report, log=True):
        post_url = self._url + '/rest/report/create'

        report.set_user(self._user)

        response = self._session.post(post_url, data=report.to_xml_string())
        if response.status_code != 201:
            if log:
                logging.debug(response.text)
            return None
        else:
            new_id = response.headers["Location"].split('/')[-1]
            report.set_id(new_id)
            if log:
                logging.debug("POST %s success" % post_url)
                logging.info("Obj url: %s" % self.get_obj_url(report))
            return report

    def report_update(self, report, log=True):
        post_url = self._url + '/rest/report/update/%s' % report.get_id()

        report.set_user(self._user)

        response = self._session.post(post_url, data=report.to_xml_string())
        if response.status_code != 201:
            if log:
                logging.debug(response.text)
            return None
        else:
            if log:
                logging.debug("UPDATE %s success" % post_url)
                logging.info("Obj url: %s" % self.get_obj_url(report))
            return report

    def report_delete_by_id(self, report_id, log=True):
        delete_url = self._url + '/rest/report/id/%s' % report_id
        response = self._session.delete(delete_url)
        if response.status_code != 204:
            return False
        else:
            if log:
                logging.debug("DELETE %s success" % delete_url)
            return True
