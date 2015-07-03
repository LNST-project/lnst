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
from types import StringType, NoneType
from xml.etree import ElementTree
from xml.etree.ElementTree import Element
from lnst.Common.Utils import recursive_dict_update
from lnst.Common.Utils import dot_to_dict

class PerfRepoException(Exception):
    pass

class PerfRepoObject(object):
    def __init__(self):
        pass

    def _set_element_atrib(self, element, name, value):
        if value != None:
            element.set(name, value)

    def to_xml(self):
        pass

    def to_xml_string(self):
        root = self.to_xml()
        return ElementTree.tostring(root)

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

class PerfRepoTestExecution(PerfRepoObject):
    def __init__(self, xml=None):
        if type(xml) is NoneType:
            self._id = None
            self._name = None
            self._started = datetime.datetime.now().isoformat()
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

    def set_id(self, id):
        self._id = id

    def set_name(self, name):
        self._name = name

    def set_started(self, date=None):
        if isinstance(date, NoneType):
            date = datetime.datetime.now()
            self._started = date.isoformat()
        else:
            self._started = date

    def set_testId(self, testId):
        if isinstance(testId, PerfRepoTest):
            self._testId = testId.get_id()
        else:
            self._testId = testId

    def set_testUid(self, testUid):
        if isinstance(testUid, PerfRepoTest):
            self._testUid = testUid.get_uid()
        else:
            self._testUid = testUid

    def get_testUid(self):
        return self._testUid

    def set_comment(self, comment):
        self._comment = comment

    def add_value(self, value):
        self._values.append(value)

    def get_values(self):
        return self._values

    def get_value(self, metric_name):
        for val in self._values:
            if val.get_metricName() == metric_name:
                return val

    def add_tag(self, tag):
        self._tags.append(tag)

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

class PerfRepoReport(PerfRepoObject):
    def __init__(self, xml=None):
        self._baselines = []
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

            self._parse_baseline_properties()
        else:
            raise PerfRepoException("Parameter xml must be"\
                                    " a string, an Element or None")

    def _parse_baseline_properties(self):
        chart = self._properties["chart0"] #TODO more charts per report?
        baseline_re = re.compile(r'baseline(\d+)')
        for key, value in chart.iteritems():
            match = baseline_re.match(key)
            if match is None:
                continue
            self._baselines.append(value)

    def get_baseline(self, index=-1):
        return self._baselines[index]

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

    def test_get_by_id(self, test_id):
        get_url = self._url + '/rest/test/id/%s' % test_id
        response = self._session.get(get_url)
        if response.status_code != 200:
            return None
        else:
            return PerfRepoTest(response.content)

    def test_get_by_uid(self, test_uid):
        get_url = self._url + '/rest/test/uid/%s' % test_uid
        response = self._session.get(get_url)
        if response.status_code != 200:
            return None
        else:
            return PerfRepoTest(response.content)

    def test_create(self, test):
        post_url = self._url + '/rest/test/create'
        response = self._session.post(post_url, data=test.to_xml_string())
        if response.status_code != 201:
            return None
        else:
            test.set_id(response.headers['Location'])
            return test

    def test_add_metric(self, test_id, metric):
        post_url = self._url + '/rest/test/id/%s/addMetric' % test_id
        response = self._session.post(post_url, data=metric.to_xml_string)
        if response.status_code != 201:
            return None
        else:
            metric.set_id(response.headers['Location'])
            return metric

    def test_remove(self, test_id):
        delete_url = self._url + '/rest/test/id/%s' % test_id
        response = self._session.delete(delete_url)
        if response.status_code != 204:
            return False
        else:
            return True

    def metric_get(self, metric_id):
        get_url = self._url + '/rest/metric/%s' % metric_id
        response = self._session.get(get_url)
        if response.status_code != 200:
            return None
        else:
            return PerfRepoMetric(response.content)

    def testExecution_get(self, testExec_id):
        get_url = self._url + '/rest/testExecution/%s' % testExec_id
        response = self._session.get(get_url)
        if response.status_code != 200:
            return None
        else:
            return PerfRepoTestExecution(response.content)

    def testExecution_create(self, testExec):
        post_url = self._url + '/rest/testExecution/create'
        response = self._session.post(post_url, data=testExec.to_xml_string())
        if response.status_code != 201:
            return None
        else:
            testExec.set_id(response.headers['Location'])
            return testExec

    def testExecution_delete(self, testExec_id):
        delete_url = self._url + '/rest/testExecution/%s' % testExec_id
        response = self._session.delete(delete_url)
        if response.status_code != 204:
            return False
        else:
            return True

    def testExecution_add_value(self, value):
        post_url = self._url + '/rest/testExecution/addValue'
        #TODO
        return self._session.post(post_url, data=value)

    def testExecution_get_attachment(self, attachment_id):
        get_url = self._url + '/rest/testExecution/attachment/%s' % \
                                                                attachment_id
        #TODO
        return self._session.get(get_url)

    def testExecution_add_attachment(self, testExec_id, attachment):
        post_url = self._url + '/rest/testExecution/%s/addAttachment' % \
                                                                testExec_id
        #TODO
        return self._session.post(post_url, data=attachment)

    def report_get_by_id(self, report_id):
        get_url = self._url + '/rest/report/id/%s' % report_id
        response = self._session.get(get_url)
        if response.status_code != 200:
            return None
        else:
            return PerfRepoReport(response.content)

    def report_create(self, report):
        #TODO not needed yet and therefore not tested
        post_url = self._url + '/rest/report/create'
        self._session.post(post_url, data=report)
        return None

    def report_delete(self, report_id):
        #TODO not needed yet and therefore not tested
        delete_url = self._url + '/rest/report/delete'
        self._session.delete(post_url)
        return None
