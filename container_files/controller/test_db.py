"""
Test database for sequential recipe execution.

When RECIPE and RECIPE_PARAMS environment variables are not set,
the container runner will execute all tests defined here in order.
"""

tests = [
    # Add more test entries as needed:
    # {
    #     "recipe_name": "SimpleNetworkRecipe",
    #     "params": {
    #         "perf_iterations": 1,
    #         "perf_duration": 10,
    #         "driver": "ice",
    #     },
    # },
    {
        "recipe_name": "SimpleNetworkRecipe",
        "params": {
            "driver": "mlx5_core",
            "perf_tool_cpu": [6],
            "dev_intr_cpu": [0],
            "perf_parallel_processes": 1,
            "offload_combinations": [
                {"gro": "on", "gso": "on", "tso": "on", "tx": "on", "rx": "on"}
            ],
            "perf_duration": 60,
            "ip_versions": ["ipv4"],
            "perf_tests": ["tcp_stream"],
            "perf_msg_sizes": [131072],
            "rx_pause_frames": False,
            "tx_pause_frames": False,
            "nic_speed": "100000",
            "nic_model": "Mellanox-MT2910_Family",
            "perf_iterations": 1,
            "net_ipv4": "192.168.220.0/24",
        },
    },
    {
        "recipe_name": "SimpleNetworkRecipe",
        "params": {
            "driver": "mlx5_core",
            "perf_tool_cpu": [6],
            "dev_intr_cpu": [0],
            "perf_parallel_processes": 1,
            "offload_combinations": [
                {"gro": "on", "gso": "on", "tso": "on", "tx": "on", "rx": "on"}
            ],
            "perf_duration": 60,
            "ip_versions": ["ipv6"],
            "perf_tests": ["tcp_stream"],
            "perf_msg_sizes": [131072],
            "rx_pause_frames": False,
            "tx_pause_frames": False,
            "nic_speed": "100000",
            "nic_model": "Mellanox-MT2910_Family",
            "perf_iterations": 1,
            "net_ipv6": "fd00:0:b100::/64",
        },
    },
]
