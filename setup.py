#!/usr/bin/env python3

"""
Install script for lnst

This script will install LNST to your system.
To install LNST, execute it as follows:

    pip3 install .

To install lnst to a different root use:

    pip3 install --prefix <path> .

"""

import re
import gzip
from time import gmtime, strftime
from setuptools import setup, find_packages
from lnst.Common.Version import lnst_version


def process_template(template_path, values):
    template_name_re = "\.in$"
    if not re.search(template_name_re, template_path):
        raise Exception("Not a template!")

    file_path = re.sub(template_name_re, "", template_path)
    t = open(template_path, "r")
    f = open(file_path, "w")
    template = t.read()
    for var, value in values.items():
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

CTL_RESOURCE_DIR = "/usr/share/lnst/"
CTL_LOGS_DIR = "~/.lnst/logs/"

SLAVE_LOGS_DIR = "/var/log/lnst"
SLAVE_CACHE_DIR = "/var/cache/lnst"

# Process templated files
TEMPLATES_VALUES = {
    "conf_dir": CONF_DIR,
    "man_dir": MAN_DIR,

    "ctl_resource_dir": CTL_RESOURCE_DIR,
    "ctl_logs_dir": CTL_LOGS_DIR,

    "slave_logs_dir": SLAVE_LOGS_DIR,
    "slave_cache_dir": SLAVE_CACHE_DIR,

    "date": strftime("%Y-%m-%d", gmtime())
}

TEMPLATES = [
    "install/lnst-ctl.conf.in",
    "install/lnst-slave.conf.in",
    "install/lnst-slave.1.in",
]

for template in TEMPLATES:
    process_template(template, TEMPLATES_VALUES)
# ---

# Pack man pages
gzip_file("install/lnst-slave.1")
# ---

LONG_DESC = """LNST

Linux Network Stack Test is a tool that supports development and execution
of automated and portable network tests.

For detailed description of the architecture of LNST please refer to
project website <https://fedorahosted.org/lnst>.
"""

SCRIPTS = ["lnst-slave"]

MAN_PAGES = [(MAN_DIR, ["install/lnst-slave.1.gz"])]

CONFIG = [(CONF_DIR, ["install/lnst-ctl.conf", "install/lnst-slave.conf"])]

BASH_COMP = [(BASH_COMP_DIR, ["install/lnst-slave.bash"])]

SCHEMAS = [(CTL_RESOURCE_DIR, ["schema-sm.rng"])]

DATA_FILES = CONFIG + MAN_PAGES + SCHEMAS + BASH_COMP

setup(name="lnst",
      version=lnst_version.version,
      description="Linux Network Stack Test",
      author="LNST Team",
      author_email="lnst-developers@lists.fedorahosted.org",
      maintainer="Ondrej Lichtner",
      maintainer_email="olichtne@redhat.com",
      url="http://lnst-project.org",
      long_description=LONG_DESC,
      platforms=["linux"],
      license=["GNU GPLv2"],
      packages=find_packages(),
      install_requires=[
          'pyyaml',
          'lxml',
          'pyroute2',
          'libvirt-python'],
      scripts=SCRIPTS,
      data_files=DATA_FILES)
