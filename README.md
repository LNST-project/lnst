# Current state

[IMPORTANT UPDATE ABOUT RECENT REPOSITORY CHANGES](https://lists.fedorahosted.org/archives/list/lnst-developers@lists.fedorahosted.org/thread/WK2PWZSUVDDJBQCJSZDR6WCJKZ44ZKVU/)

We recently went through some breaking changes to the repository code base as
outlined in the linked email. These have been coming for a long time as most of
our development was focused on the 'next' branch (now renamed to master).

A lot of the 'next' functionality is ready to be used for testing purposes but
we've yet to mark individual library APIs as 'stable' so no guarantees for
backwards compatibility are yet in place.

This also means that many of our documentation resources outlining how to write
recipes on the wiki are also out of date. We'll soon start working on these but
please be patient with us.

If you're interested in helping out we accept code contributions via Patches
submitted to our mailing list <lnst-developers@lists.fedorahosted.org>.

Likewise if you're interested in trying out LNST and are having trouble with
setting stuff up because of the current state of our documentation feel free to
reach out to us either on the mailing list or on #lnst @ freenode.net irc
channel.


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

## Authors/Contributors

* Jiri Pirko <jiri@resnulli.us>
* Jan Tluka <jtluka@redhat.com>
* Ondrej Lichtner <olichtne@redhat.com> (current maintainer)
* Jozef Urbanovsky <jurbanov@redhat.com>
* Christos Sfakianakis (not active anymore)
* Jiri Prochazka (not active anymore)
* Kamil Jerabek (not active anymore)
* Jiri Zupka (not active anymore)
* Radek Pazdera (not active anymore)

## How to contact us

* Git Source Tree: https://github.com/jpirko/lnst
* Mailing List:  <lnst-developers@lists.fedorahosted.org>
* IRC channel: #lnst @ freenode.net

## License

**Copyright (C) 2011-2020 Red Hat, Inc.**

LNST is distributed under GNU General Public License version 2. See the file
"COPYING" in the source distribution for information on terms & conditions
for accessing and otherwise using LNST.
