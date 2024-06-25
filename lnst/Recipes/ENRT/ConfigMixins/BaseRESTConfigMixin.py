import time
import logging
import requests
from requests.exceptions import RequestException

from lnst.Common.LnstError import LnstError
from lnst.Common.Parameters import BoolParam, StrParam


class BaseRESTConfigMixin:
    api_url = StrParam()
    rest_user = StrParam()
    rest_password = StrParam()
    ssl_verify = BoolParam(default=True, mandatory=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.BASE_DELAY = 1

    @staticmethod
    def __get_request_function(method: str):
        try:
            return getattr(requests, method)
        except AttributeError:
            raise LnstError(f"Method {method} is not supported")

    def __build_request(self, endpoint: str, **kwargs):
        kwargs["url"] = self.params.api_url + endpoint

        if self.params.rest_user and self.params.rest_password:
            kwargs["auth"] = (self.params.rest_user, self.params.rest_password)

        kwargs["verify"] = self.params.ssl_verify

        return kwargs

    def api_request(self, method: str, endpoint: str, response_code: int = 200, tries: int = 7, **kwargs) -> bytes:
        request = self.__build_request(endpoint, **kwargs)
        req_func = self.__get_request_function(method)

        for i in range(1, tries+1):  # i starts from 1
            try:
                response = req_func(**request)
            except RequestException as e:
                delay = self.BASE_DELAY * 2 ** i

                logging.error(
                    f"API request ({i}/{tries}) failed. Retrying in {delay} seconds.",
                    exc_info=True,
                )

                time.sleep(delay)
                continue
            
            break  # request was successful
        else:
            raise LnstError(f"API request failed after {tries} tries")

        if response.status_code != response_code:
            raise LnstError(f"Request failed with status code {response.status_code}")

        logging.debug("API response: %s", response.content)

        return response
