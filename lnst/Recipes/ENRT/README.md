# ENRT Recipes

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
* it should be possible to very easily extend the recipes with new features such
    as more types of parallel or sequential measurements, more types of
    Evaluations for different types of measurements, or to be able to switch out
    and use different measurement tools

The resulting design is split into several parts that interact with each other
in a specific way:

* [BaseEnrtRecipe](BaseEnrtRecipe.py) serves as the base class for all the
  specific test scenarios we want to test. Defines the common test loop and the
  default implementation for configuration generators used in this common test
  loop.
* [ConfigMixins](ConfigMixins/README.md) package contains the various types of
  "SubConfig" mixin classes, these are classes that implement some form of
  configuration on test machine(s) which can be reused between mutliple recipes,
  but can often times be looped over to try different variations of the
  configuration. A good example is configuration of hardware offloads, it's
  relevant to test it for many different test scenarios, but only some
  combinations of offloads make sense based on the scenario and we often time
  want to test more than one combination
* Specific test scenario implementation that defines the requirements and the
  main configuration for the specific scenario that we want to test. It also
  defines the combination of various "SubConfig" configurations that we want to
  include by adding them to it's inheritance tree. If required the recipe can
  also override any of the default functionality defined by it's parent classes,
  a good example could be the generator method for creating various
  configurations for flow performance measurement.
