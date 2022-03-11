"""Stromer module for Home Assistant Core."""

__version__ = "0.0.3a0"

import json
import logging
import re
from urllib.parse import urlencode

import aiohttp

LOGGER = logging.getLogger(__name__)


class Stromer:
    """Set up Stromer."""

    def __init__(self, username, password, client_id, client_secret, timeout=60):
        self.bike = {}
        self.status = {}
        self.position = {}

        self._timeout = timeout
        self._username = username
        self._password = password
        self._client_id = client_id
        self._client_secret = client_secret

        self._code = None
        self._token = None

        self.bike_id = None
        self.bike_name = None
        self.bike_model = None

    async def stromer_connect(self):
        aio_timeout = aiohttp.ClientTimeout(total=self._timeout)
        self._websession = aiohttp.ClientSession(timeout=aio_timeout)

        # Retrieve access token
        await self.stromer_get_code()
        # LOGGER.debug("Stromer code: {}".format(self._code))

        # Retrieve access token
        await self.stromer_get_access_token()
        # LOGGER.debug("Stromer token: {}".format(self._token))

        try:
            await self.stromer_update()
        except Exception as e:
            LOGGER.error("Stromer unable to update: {}".format(e))

        LOGGER.debug("Stromer connected!")

        return self.status

    async def stromer_update(self):
        try:
            self.bike = await self.stromer_call_api(endpoint="bike/")
            LOGGER.debug("Stromer bike: {}".format(self.bike))

            self.bike_id = self.bike["bikeid"]
            self.bike_name = self.bike["nickname"]
            self.bike_model = self.bike["biketype"]

            endpoint = f"bike/{self.bike_id}/state/"
            data = {"cached": "false"}
            # LOGGER.debug("Stromer endpoint: {}".format(endpoint))
            self.status = await self.stromer_call_api(endpoint=endpoint, data=data)
            LOGGER.debug("Stromer status: {}".format(self.status))

            endpoint = f"bike/{self.bike_id}/position/"
            self.position = await self.stromer_call_api(endpoint=endpoint, data=data)
            LOGGER.debug("Stromer position: {}".format(self.position))
        except Exception as e:
            LOGGER.error("Stromer error: api call failed: {}".format(e))

    async def stromer_get_code(self):
        base_url = "https://api3.stromer-portal.ch"
        url = f"{base_url}/users/login/"
        res = await self._websession.get(url)
        cookie = res.headers.get("Set-Cookie")
        pattern = "=(.*?);"
        csrftoken = re.search(pattern, cookie).group(1)

        qs = urlencode(
            {
                "client_id": self._client_id,
                "response_type": "code",
                "redirect_url": "stromerauth://auth",
                "scope": "bikeposition bikestatus bikeconfiguration bikelock biketheft bikedata bikepin bikeblink userprofile",
            }
        )

        data = {
            "password": self._password,
            "username": self._username,
            "csrfmiddlewaretoken": csrftoken,
            "next": "/o/authorize/?" + qs,
        }

        res = await self._websession.post(
            url, data=data, headers=dict(Referer=url), allow_redirects=False
        )
        next_loc = res.headers.get("Location")
        next_url = f"{base_url}{next_loc}"
        res = await self._websession.get(next_url, allow_redirects=False)
        self._code = res.headers.get("Location")
        self._code = self._code.split("=")[1]

    async def stromer_get_access_token(self):
        url = "https://api3.stromer-portal.ch/o/token/"
        data = {
            "grant_type": "authorization_code",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "code": self._code,
            "redirect_uri": "stromerauth://auth",
        }

        res = await self._websession.post(url, data=data)
        token = json.loads(await res.text())
        self._token = token["access_token"]

    async def stromer_call_api(self, endpoint, data={}):
        url = f"https://api3.stromer-portal.ch/rapi/mobile/v2/{endpoint}"
        headers = {"Authorization": f"Bearer {self._token}"}
        # LOGGER.debug("token %s" % self._token)
        res = await self._websession.get(url, headers=headers, data={})
        ret = json.loads(await res.text())
        # LOGGER.debug("ret %s" % ret)
        # LOGGER.debug("res status %s" % res.status)
        return ret["data"][0]
