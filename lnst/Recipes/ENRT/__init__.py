'''
ENRT Recipes
------------

ENRT stands for Early Network Regression Testing, which was the name of the
project a couple of years back when we started developing this set of tests
when we were still using the Legacy LNST API.

This package aims to reimplement the same set of tests, using the new LNST-next
APIs, while fully utilizing Python to address the largest problems with the old
implementation:

* large amounts of code duplication
* copy paste errors caused by code duplication
* very hard to maintain the test set and fix bugs
* very hard to add new tests due to limitations of the old LNST Framework

With that in mind, the main goals for this reimplementation were as follows:

* reduce code duplication as much as possible by utilizing class inheritance
* separate individual types of configurations into smaller Mixin classes that
  can be mixed and matched based on what a specific Test scenario requires
* writing new test scenarios should be very quick because it should be possible
  to reuse most of the functionality already defined
* it should be possible to very easily extend the recipes with new features
  such as more types of parallel or sequential measurements, more types of
  Evaluations for different types of measurements, or to be able to switch out
  and use different measurement tools

The resulting design is split into several parts that interact with each other
in a specific way:

* BaseEnrtRecipe serves as the base class for all the specific test scenarios
  we want to test. Defines the common test loop and the default implementation
  for configuration generators used in this common test loop.
* ConfigMixins package contains the various types of "SubConfig" mixin classes,
  these are classes that implement some form of configuration on test
  machine(s) which can be reused between mutliple recipes, but can often times
  be looped over to try different variations of the configuration. A good
  example is configuration of hardware offloads, it's relevant to test it for
  many different test scenarios, but only some combinations of offloads make
  sense based on the scenario and we often time want to test more than one
  combination
* Specific test scenario implementation that defines the requirements and the
  main configuration for the specific scenario that we want to test. It also
  defines the combination of various "SubConfig" configurations that we want to
  include by adding them to it's inheritance tree. If required the recipe can
  also override any of the default functionality defined by it's parent
  classes, a good example could be the generator method for creating various
  configurations for flow performance measurement.

'''
from lnst.Recipes.ENRT.SimpleNetworkRecipe import SimpleNetworkRecipe
from lnst.Recipes.ENRT.BondRecipe import BondRecipe
from lnst.Recipes.ENRT.DoubleBondRecipe import DoubleBondRecipe
from lnst.Recipes.ENRT.DoubleTeamRecipe import DoubleTeamRecipe
from lnst.Recipes.ENRT.IpsecEspAeadRecipe  import IpsecEspAeadRecipe
from lnst.Recipes.ENRT.IpsecEspAhCompRecipe import IpsecEspAhCompRecipe
from lnst.Recipes.ENRT.NoVirtOvsVxlanRecipe import NoVirtOvsVxlanRecipe
from lnst.Recipes.ENRT.OvS_DPDK_PvP import OvSDPDKPvPRecipe
from lnst.Recipes.ENRT.OvSDPDKBondRecipe import OvSDPDKBondRecipe
from lnst.Recipes.ENRT.PingFloodRecipe import PingFloodRecipe
from lnst.Recipes.ENRT.SimpleMacsecRecipe import SimpleMacsecRecipe
from lnst.Recipes.ENRT.ShortLivedConnectionsRecipe import ShortLivedConnectionsRecipe
from lnst.Recipes.ENRT.TeamRecipe import TeamRecipe
from lnst.Recipes.ENRT.TeamVsBondRecipe import TeamVsBondRecipe
from lnst.Recipes.ENRT.VirtOvsVxlanRecipe import VirtOvsVxlanRecipe
from lnst.Recipes.ENRT.VirtualBridgeVlanInGuestMirroredRecipe import VirtualBridgeVlanInGuestMirroredRecipe
from lnst.Recipes.ENRT.VirtualBridgeVlanInGuestRecipe import VirtualBridgeVlanInGuestRecipe
from lnst.Recipes.ENRT.VirtualBridgeVlanInHostMirroredRecipe import VirtualBridgeVlanInHostMirroredRecipe
from lnst.Recipes.ENRT.VirtualBridgeVlanInHostRecipe import VirtualBridgeVlanInHostRecipe
from lnst.Recipes.ENRT.VirtualBridgeVlansOverBondRecipe import VirtualBridgeVlansOverBondRecipe
from lnst.Recipes.ENRT.VirtualOvsBridgeVlanInGuestMirroredRecipe import VirtualOvsBridgeVlanInGuestMirroredRecipe
from lnst.Recipes.ENRT.VirtualOvsBridgeVlanInGuestRecipe import VirtualOvsBridgeVlanInGuestRecipe
from lnst.Recipes.ENRT.VirtualOvsBridgeVlanInHostMirroredRecipe import VirtualOvsBridgeVlanInHostMirroredRecipe
from lnst.Recipes.ENRT.VirtualOvsBridgeVlanInHostRecipe import VirtualOvsBridgeVlanInHostRecipe
from lnst.Recipes.ENRT.VirtualOvsBridgeVlansOverBondRecipe import VirtualOvsBridgeVlansOverBondRecipe
from lnst.Recipes.ENRT.VlansOverBondRecipe import VlansOverBondRecipe
from lnst.Recipes.ENRT.VlansOverTeamRecipe import VlansOverTeamRecipe
from lnst.Recipes.ENRT.VlansRecipe import VlansRecipe
from lnst.Recipes.ENRT.VxlanMulticastRecipe import VxlanMulticastRecipe
from lnst.Recipes.ENRT.VxlanRemoteRecipe import VxlanRemoteRecipe
from lnst.Recipes.ENRT.GreTunnelRecipe import GreTunnelRecipe
from lnst.Recipes.ENRT.GreTunnelOverBondRecipe import GreTunnelOverBondRecipe
from lnst.Recipes.ENRT.Ip6GreTunnelRecipe import Ip6GreTunnelRecipe
from lnst.Recipes.ENRT.Ip6GreNetnsTunnelRecipe import Ip6GreNetnsTunnelRecipe
from lnst.Recipes.ENRT.SitTunnelRecipe import SitTunnelRecipe
from lnst.Recipes.ENRT.IpIpTunnelRecipe import IpIpTunnelRecipe
from lnst.Recipes.ENRT.Ip6TnlTunnelRecipe import Ip6TnlTunnelRecipe
from lnst.Recipes.ENRT.GeneveTunnelRecipe import GeneveTunnelRecipe
from lnst.Recipes.ENRT.GeneveLwtTunnelRecipe import GeneveLwtTunnelRecipe
from lnst.Recipes.ENRT.L2TPTunnelRecipe import L2TPTunnelRecipe

from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.BaseTunnelRecipe import BaseTunnelRecipe
