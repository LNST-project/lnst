from abc import ABC, abstractmethod

from lnst.Controller.Recipe import RecipeRun


class RunSummaryFormatter(ABC):
    @abstractmethod
    def format_run(self, run: RecipeRun) -> str:
        ...

