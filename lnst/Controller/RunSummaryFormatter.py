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

from lnst.Common.Colours import decorate_with_preset
from lnst.Controller.Common import ControllerError
from lnst.Controller.MachineMapper import format_match_description
from lnst.Controller.Recipe import BaseRecipe, RecipeRun
from lnst.Controller.RecipeResults import BaseResult, JobResult, Result
from lnst.Controller.RecipeResults import JobStartResult, JobFinishResult
from lnst.Controller.RecipeResults import ResultLevel

class RunFormatterException(ControllerError):
    pass

class RunSummaryFormatter(object):
    def __init__(self, level=ResultLevel.IMPORTANT):
        #TODO changeable format?
        self._format = ""
        self._level = level

    def _format_success(self, success):
        if success:
            return decorate_with_preset("PASS", "pass")
        else:
            return decorate_with_preset("FAIL", "fail")

    def _format_source(self, res):
        if isinstance(res, JobResult):
            return "Host {} job {}".format(res.job.host.hostid, res.job.id)
        elif isinstance(res, Result):
            return "TestResult:"
        else:
            return ""

    def _format_data(self, data, prefix="    ", level=1):
        output = []
        if data is not None:
            if isinstance(data, dict):
                for key, value in data.items():
                    output.append("{pref}{key}:".format(pref=level*prefix,
                                                        key=key))
                    nest_res = self._format_data(value, level=level+1)
                    if len(nest_res) == 1:
                        output[-1] += " " + nest_res[0].lstrip()
                    else:
                        output.extend(nest_res)
            elif isinstance(data, list):
                for i, v in enumerate(data):
                    output.append("{pref}item {i}:".format(pref=level*prefix,
                                                           i=i))
                    output.extend(self._format_data(v, level=level+1))
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
                            res.success == False or res.level <= self._level]
        overall_result = True
        for i, res in enumerate(filtered_results):
            overall_result = overall_result and res.success

            try:
                next_res = filtered_results[i+1]
                if (isinstance(res, JobStartResult) and
                    isinstance(next_res, JobFinishResult) and
                    res.job.host == next_res.job.host and
                    res.job.id == next_res.job.id and
                    res.success):
                    continue
            except IndexError:
                pass

            output_lines.append("{res}\t{src}\t{desc}".format(
                res = self._format_success(res.success),
                src = self._format_source(res),
                desc = res.short_desc))

            output_lines.extend(self._format_data(res.data))

        output_lines.append("Overall result of this Run: {}".
                            format(self._format_success(overall_result)))

        return "\n".join(output_lines)
