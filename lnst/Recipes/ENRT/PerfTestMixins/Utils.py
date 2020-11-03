from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import BaseFlowMeasurement

def get_flow_measurements_from_config(perf_config):
    flow_measurements = [ m for m in perf_config.measurements if isinstance(m, BaseFlowMeasurement) ]
    return flow_measurements
