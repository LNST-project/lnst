"""
Defines the RunSummaryFormatter class which is can be used to process a
RecipeRun object to return a formatted run summary string.

Copyright 2018 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.Utils import indent
from lnst.Common.Colours import decorate_with_preset
from lnst.Controller.Common import ControllerError
from lnst.Controller.MachineMapper import format_match_description
from lnst.Controller.Recipe import RecipeRun
from lnst.Controller.RecipeResults import DeviceConfigResult, JobResult, Result
from lnst.Controller.RecipeResults import JobStartResult, JobFinishResult
from lnst.Controller.RecipeResults import ResultLevel, ResultType

class RunFormatterException(ControllerError):
    pass

class RunSummaryFormatter(object):
    def __init__(self, level=ResultLevel.IMPORTANT, colourize=False):
        #TODO changeable format?
        self._format = ""
        self._level = level
        self._colourize = colourize

    def _format_result(self, res):
        res = str(res)
        if self._colourize:
            return decorate_with_preset(
                res,
                res.lower()
            )

        return res

    def _format_source(self, res):
        if isinstance(res, JobResult):
            return "Host {} job {}".format(res.job.host.hostid, res.job.id)
        elif isinstance(res, Result):
            return "TestResult:"
        elif isinstance(res, DeviceConfigResult):
            return res.__class__.__name__
        else:
            return res.__class__.__name__

    def _format_data(self, data, prefix="    ", level=1):
        output = []
        if data is not None:
            if isinstance(data, dict):
                for key, value in list(data.items()):
                    output.append("{pref}{key}:".format(pref=level*prefix,
                                                        key=key))
                    nest_res = self._format_data(value, level=level+1)
                    if len(nest_res) == 1:
                        output[-1] += " " + nest_res[0].lstrip()
                    else:
                        output.extend(nest_res)
            elif isinstance(data, list):
                for i, v in enumerate(data):
                    formatted_v = self._format_data(v, level=level+1)

                    if len(formatted_v) == 1:
                        output.append("{pref}item {i}: {value}".format(
                            pref=level*prefix,
                            i=i,
                            value=formatted_v[0].lstrip()))
                    else:
                        output.append("{pref}item {i}:".format(
                            pref=level*prefix, i=i))
                        output.extend(formatted_v)
            else:
                for line in str(data).split('\n'):
                    output.append("{pref}{val}".format(pref=level*prefix,
                                                       val=line))
        return output

    def format_run(self, run):
        if not isinstance(run, RecipeRun):
            raise RunFormatterException("run must be a RecipeRun instance.")

        output_lines = []
        output_lines.append("RUN SUMMARY")
        output_lines.append("Description:")
        if run.description:
            output_lines.extend(str(run.description).split("\n"))

        output_lines.extend(format_match_description(run.match).split('\n'))

        filtered_results = [res for res in run.results if
                            res.result == ResultType.FAIL or res.level <= self._level]
        for i, res in enumerate(filtered_results):
            try:
                next_res = filtered_results[i+1]
                if (isinstance(res, JobStartResult) and
                    isinstance(next_res, JobFinishResult) and
                    res.job.host == next_res.job.host and
                    res.job.id == next_res.job.id and
                    res.result):
                    continue
            except IndexError:
                pass

            output_lines.append("{res} {result_index}_{src}{desc}".format(
                res = self._format_result(res.result),
                result_index=run.results.index(res),
                src = self._format_source(res),
                desc = ("\t{}".format(res.description)
                    if res.description.count('\n') == 0
                    else "\n{}".format(indent(res.description, 4)))))

            if res.data_level <= self._level:
                output_lines.extend(self._format_data(res.data))

        output_lines.append("Overall result of this Run: {}".
                            format(self._format_result(run.overall_result)))

        return "\n".join(output_lines)
