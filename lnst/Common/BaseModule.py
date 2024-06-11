from abc import abstractmethod


class BaseModule:
    def __init__(self, **kwargs):
        self._orig_kwargs = kwargs.copy()
        self._res_data = None

    @abstractmethod
    def run(self):
        pass

    def _get_res_data(self):
        return self._res_data

    def __repr__(self):
        return "{}({})".format(
            self.__class__.__name__,
            ", ".join(
                [
                    "{}={}".format(k, repr(v))
                    for k, v in self._orig_kwargs.items()
                ]
            ),
        )

