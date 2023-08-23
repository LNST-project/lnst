# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
import pathlib
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(pathlib.Path(__file__).parent.absolute(), "../../")
    ),
)


# -- Project information -----------------------------------------------------

project = 'lnst'
copyright = '2020, Jiri Pirko'
author = 'Jiri Pirko'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
if os.environ.get("READTHEDOCS") == "True":
    html_theme = 'sphinx_rtd_theme'
else:
    html_theme = 'classic'
# html_theme = 'classic'
# html_theme_options = {
#     "body_min_width": "100%",
#     "body_max_width": "100%",
# }

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

autodoc_default_options = {
    'member-order': 'bysource',
}

autodoc_inherit_docstrings = False

autodoc_mock_imports = ["pyroute2", "libvirt", "ethtool", "lxml", "yaml", "podman", "psutil"]

master_doc = "index"
