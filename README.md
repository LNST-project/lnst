# LNST - Linux Network Stack Test #

Linux Network Stack Test is a tool that supports development and execution
of automated and portable network tests. For detailed description of the
architecture of LNST please refer to project website (link listed on
Internet Resources bellow).


## Install

LNST can be installed using python's distutils.

```bash
su
./setup.py install
```

### Prerequirement

Make sure python-devel, dbus-devel and dbus-glib-devel packages are installed:
```bash
su
dnf install python-devel dbus-devel dbus-glib-devel
```

In addition the following python libraries should be installed:

Using package manager:
```
su
dnf install dbus-python-devel
dnf install python-pyroute2
```

Or using `pip`:
```bash
su
pip install pyroute2
pip install dbus-python
```

## Authors

* Jiri Pirko <jiri@resnulli.us>
* Jan Tluka <jtluka@redhat.com>
* Ondrej Lichtner <olichtne@redhat.com>
* Jiri Prochazka <jprochaz@redhat.com>
* Jiri Zupka <jzupka@redhat.com>
* Radek Pazdera <radek@pazdera.co.uk>


## Internet Resources

* Project Wiki:     https://github.com/jpirko/lnst/wiki
* Documentation:    https://github.com/jpirko/lnst/wiki#learn
* Git Source Tree:  https://github.com/jpirko/lnst
* Mailing List:     <lnst-developers@lists.fedorahosted.org>


## License

**Copyright (C) 2011-2015 Red Hat, Inc.**

LNST is distributed under GNU General Public License version 2. See the file
"COPYING" in the source distribution for information on terms & conditions
for accessing and otherwise using LNST.
