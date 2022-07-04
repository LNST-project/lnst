from lnst.Controller.RecipeResults import ResultType
from lnst.RecipeCommon.BaseResultEvaluator import BaseResultEvaluator

class ZeroPassPingEvaluator(BaseResultEvaluator):
    def evaluate_results(self, recipe, result):
        result_status = ResultType.PASS
        trans_packets = int(result['trans_pkts'])
        recv_packets = int(result['recv_pkts'])

        if recv_packets > 0:
            result_status = ResultType.FAIL
            result_text = [
                'expected zero packets but {} of {} packets '
                'were received'.format(
                    recv_packets, trans_packets)
                ]
        else:
            result_text = ['received {} of {} packets as expected'.format(
                recv_packets, trans_packets)
                ]

        recipe.add_result(result_status, "\n".join(result_text))
