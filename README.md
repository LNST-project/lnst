# Current state

[IMPORTANT UPDATE ABOUT RECENT REPOSITORY CHANGES](https://lists.fedorahosted.org/archives/list/lnst-developers@lists.fedorahosted.org/thread/WK2PWZSUVDDJBQCJSZDR6WCJKZ44ZKVU/)

We recently went through some breaking changes to the repository code base as
outlined in the linked email. These have been coming for a long time as most of
our development was focused on the 'next' branch (now renamed to master).

A lot of the 'next' functionality is ready to be used for testing purposes but
we've yet to mark individual library APIs as 'stable' so no guarantees for
backwards compatibility are yet in place.

# LNST - Linux Network Stack Test #

Linux Network Stack Test is a tool that supports development and execution
of automated and portable network tests. For detailed description of the
architecture of LNST please refer to project website (link listed on
Internet Resources bellow).

## Install

Installation and a simple Hello world example is available at
[Installation](docs/source/installation.rst)

## Documentation

Documentation is available in the `docs/` directory, you can build it with
`make html` using *Sphinx*.

The built documentation is also available online on https://lnst.readthedocs.io/en/latest/

The documentation is not fully complete so you may not find all of what you're
looking for so feel free to reach out to us if you have any questions.

## Contributing

If you're interested in helping out we accept code contributions via Patches
submitted to our mailing list <lnst-developers@lists.fedorahosted.org>.

Feel free to also report issues or submit pull requests.

## Authors/Contributors

* Jiri Pirko <jiri@resnulli.us>
* Jan Tluka <jtluka@redhat.com>
* Ondrej Lichtner <olichtne@redhat.com> (current maintainer)
* Jozef Urbanovsky <jurbanov@redhat.com>
* Perry Gagne <pgagne@redhat.com>
* Christos Sfakianakis (not active anymore)
* Jiri Prochazka (not active anymore)
* Kamil Jerabek (not active anymore)
* Jiri Zupka (not active anymore)
* Radek Pazdera (not active anymore)

## How to contact us

* Git Source Tree: https://github.com/LNST-project/lnst
* Mailing List:  <lnst-developers@lists.fedorahosted.org>

We currently don't have an irc channel due to the freenode situation and since
it wasn't exactly actively used we haven't created a new one yet.

## License

**Copyright (C) 2011-2021 Red Hat, Inc.**

LNST is distributed under GNU General Public License version 2. See the file
"COPYING" in the source distribution for information on terms & conditions
for accessing and otherwise using LNST.
