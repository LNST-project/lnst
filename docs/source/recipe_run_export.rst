Export/Import of Recipe Runs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Recipe runs can be exported to a file for for later analysis.
For example, to gather data like  CPU and iperf statistic when onboarding a new recipe.

The data that is exported is the instance of :py:class:`lnst.Controller.Recipe.RecipeRun` that was run.

The :py:class:`RecipeRun` object is "pickled" and compressed with LZMA/XZ compression using :py:mod:`lzma`.

By default the file will be contain a file extension `.lrc` which stands for "LNST Run, Compressed".

Use :py:meth:`export_recipe_run` to export and :py:meth:`import_recipe_run` to import.

.. autofunction:: lnst.Controller.Recipe.export_recipe_run

.. autofunction:: lnst.Controller.Recipe.import_recipe_run
