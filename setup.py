#!/usr/bin/env python2
"""
Install script for lnst

This script will install both lnst controller and slave
to your system. To install LNST, execute it as follows:

    ./setup.py install

To install lnst to a different root use:

    .setup.py install --root=<path>

"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import sys
import re
import gzip
import os
from time import gmtime, strftime
from distutils.core import setup
from lnst.Common.Version import LNSTMajorVersion

def process_template(template_path, values):
    template_name_re = "\.in$"
    if not re.search(template_name_re, template_path):
        raise Exception("Not a template!")

    file_path = re.sub(template_name_re, "", template_path)
    t = open(template_path, "r")
    f = open(file_path, "w")
    template = t.read()
    for var, value in values.iteritems():
        template = template.replace("@%s@" % var, value)
    f.write(template)
    f.close()
    t.close()

def gzip_file(path):
    src = open(path, "rb")
    dst = gzip.open(path + ".gz", "wb")
    dst.writelines(src)
    dst.close()
    src.close()

# Various paths
CONF_DIR = "/etc/"
BASH_COMP_DIR = CONF_DIR + "bash_completion.d/"
MAN_DIR = "/usr/share/man/man1/"

CTL_MODULES_LOCATIONS = "/usr/share/lnst/test_modules/"
CTL_TOOLS_LOCATIONS = "/usr/share/lnst/test_tools/"
CTL_RESOURCE_DIR = "/usr/share/lnst/"
CTL_LOGS_DIR = "~/.lnst/logs/"

SLAVE_LOGS_DIR = "/var/log/lnst"
SLAVE_CACHE_DIR = "/var/cache/lnst"

# Process templated files
TEMPLATES_VALUES = {
"conf_dir": CONF_DIR,
"man_dir": MAN_DIR,

"ctl_modules_locations": CTL_MODULES_LOCATIONS,
"ctl_tools_locations": CTL_TOOLS_LOCATIONS,
"ctl_resource_dir": CTL_RESOURCE_DIR,
"ctl_logs_dir": CTL_LOGS_DIR,

"slave_logs_dir": SLAVE_LOGS_DIR,
"slave_cache_dir": SLAVE_CACHE_DIR,

"date": strftime("%Y-%m-%d", gmtime())
}

TEMPLATES = [
"install/lnst-ctl.conf.in",
"install/lnst-slave.conf.in",
"install/lnst-ctl.1.in",
"install/lnst-slave.1.in",
"install/lnst-pool-wizard.1.in"
]

for template in TEMPLATES:
    process_template(template, TEMPLATES_VALUES)
# ---

# Pack man pages
gzip_file("install/lnst-ctl.1")
gzip_file("install/lnst-slave.1")
gzip_file("install/lnst-pool-wizard.1")
# ---


LONG_DESC = """LNST

Linux Network Stack Test is a tool that supports development and execution
of automated and portable network tests.

For detailed description of the architecture of LNST please refer to
project website <https://fedorahosted.org/lnst>.
"""

PACKAGES = ["lnst", "lnst.Common", "lnst.Controller", "lnst.Slave",
            "lnst.RecipeCommon" ]
SCRIPTS = ["lnst-ctl", "lnst-slave", "lnst-pool-wizard"]

RECIPE_FILES = []
for dirpath, dirnames, files in os.walk("recipes/"):
    if len(files) > 0:
        RECIPE_FILES.append((CTL_RESOURCE_DIR + dirpath + "/",
                             [dirpath + "/" + f for f in files]))

TEST_MODULES = [
    (CTL_MODULES_LOCATIONS,
        ["test_modules/DummyFailing.py",
         "test_modules/Icmp6Ping.py",
         "test_modules/IcmpPing.py",
         "test_modules/Iperf.py",
         "test_modules/Iperf3.py",
         "test_modules/Multicast.py",
         "test_modules/NetCat.py",
         "test_modules/Netperf.py",
         "test_modules/PacketAssert.py",
         "test_modules/PktCounter.py",
         "test_modules/PktgenTx.py",
         "test_modules/LinkNeg.py",
         "test_modules/Custom.py",
         "test_modules/TCPConnection.py"]
    )
]

MULTICAST_TEST_TOOLS = [
    (CTL_TOOLS_LOCATIONS + "multicast",
        ["test_tools/multicast/igmp_utils.h",
         "test_tools/multicast/lnst-setup.sh",
         "test_tools/multicast/Makefile",
         "test_tools/multicast/multicast_utils.h",
         "test_tools/multicast/parameters_igmp.h",
         "test_tools/multicast/parameters_multicast.h",
         "test_tools/multicast/README",
         "test_tools/multicast/sockopt_utils.h"]),
    (CTL_TOOLS_LOCATIONS + "multicast/client",
        ["test_tools/multicast/client/send_igmp_query.c",
         "test_tools/multicast/client/send_simple.c"]),
    (CTL_TOOLS_LOCATIONS + "multicast/offline",
        ["test_tools/multicast/offline/max_groups.c",
         "test_tools/multicast/offline/sockopt_block_source.c",
         "test_tools/multicast/offline/sockopt_if.c",
         "test_tools/multicast/offline/sockopt_loop.c",
         "test_tools/multicast/offline/sockopt_membership.c",
         "test_tools/multicast/offline/sockopt_source_membership.c",
         "test_tools/multicast/offline/sockopt_ttl.c"]),
    (CTL_TOOLS_LOCATIONS + "multicast/server",
        ["test_tools/multicast/server/recv_block_source.c",
         "test_tools/multicast/server/recv_membership.c",
         "test_tools/multicast/server/recv_simple.c",
         "test_tools/multicast/server/recv_source_membership.c"]),
    (CTL_TOOLS_LOCATIONS + "tcp_conn",
        ["test_tools/tcp_conn/lnst-setup.sh",
         "test_tools/tcp_conn/Makefile",
         "test_tools/tcp_conn/tcp_connect.c",
         "test_tools/tcp_conn/tcp_listen.c"])
]

MAN_PAGES = [(MAN_DIR, ["install/lnst-ctl.1.gz", "install/lnst-slave.1.gz",
                        "install/lnst-pool-wizard.1.gz"])]

CONFIG = [(CONF_DIR, ["install/lnst-ctl.conf", "install/lnst-slave.conf"])]

BASH_COMP = [(BASH_COMP_DIR, ["install/lnst-ctl.bash",
                              "install/lnst-slave.bash",
                              "install/lnst-pool-wizard.bash"])]

SCHEMAS = [(CTL_RESOURCE_DIR, ["schema-recipe.rng", "schema-sm.rng"])]

RESULT_XSLT_DATA = [(CTL_RESOURCE_DIR + "result_xslt/",
                     ["result_xslt/" + f for f in os.listdir("result_xslt")])]

DATA_FILES = CONFIG + TEST_MODULES + MULTICAST_TEST_TOOLS + MAN_PAGES + \
             SCHEMAS + BASH_COMP + RECIPE_FILES + RESULT_XSLT_DATA

setup(name="lnst",
    version=LNSTMajorVersion,
    description="Linux Network Stack Test",
    author="LNST Team",
    author_email="lnst-developers@lists.fedorahosted.org",
    maintainer="Jiri Pirko",
    maintainer_email="jiri@resnulli.us",
    url="http://lnst-project.org",
    long_description=LONG_DESC,
    platforms=["linux"],
    license=["GNU GPLv2"],
    packages=PACKAGES,
    scripts=SCRIPTS,
    data_files=DATA_FILES)
