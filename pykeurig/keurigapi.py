import asyncio
import json
import logging
import time

from typing import Callable, Dict, Hashable, Optional, Tuple
import uuid

import httpx

from signalrcore.hub_connection_builder import HubConnectionBuilder

from pykeurig.const import (API_URL, BREW_CATEGORY_CUSTOM, BREW_CATEGORY_FAVORITE, 
    BREW_CATEGORY_ICED, BREW_CATEGORY_RECOMMENDED, BREW_CATEGORY_WATER, BREW_COFFEE, 
    BREW_HOT_WATER, BREW_OVER_ICE, BREWER_STATUS_READY, CLIENT_ID, COMMAND_NAME_BREW, 
    COMMAND_NAME_CANCEL_BREW, COMMAND_NAME_OFF, COMMAND_NAME_ON, FAVORITE_BREW_MODE, FAVORITE_MODEL_NAME, 
    HEADER_OCP_SUBSCRIPTION_KEY, HEADER_USER_AGENT, NODE_APPLIANCE_STATE, 
    NODE_BREW_STATE, NODE_POD_STATE, NODE_SW_INFO, POD_STATUS_EMPTY, STATUS_ON, 
    Intensity, Size, Temperature)


_LOGGER = logging.getLogger(__name__)

class KeurigApi:
    def __init__(self, timeout = 10):
        self._access_token = None
        self._token_expires_at = None
        self._refresh_token = None
        self._customer_id = None
        self.timeout = timeout

    async def login(self, email: str, password: str):
        """Logs you into the Keurig API"""
        try:
            data = {'grant_type': 'password', 'client_id': CLIENT_ID, 'username': email, 'password': password}
            client = httpx.AsyncClient()
            client.headers = self._get_headers()
            client.headers.update({'Accept-Encoding': 'identity'})

            endpoint = f"{API_URL}api/v2/oauth/token"
            res = await client.post(endpoint, json=data, timeout=self.timeout)
            res.raise_for_status()

            json_result = res.json()

            self._access_token = json_result['access_token']
            self._token_expires_at = time.time() + json_result['expires_in'] - 120
            self._refresh_token = json_result['refresh_token']
        except:
            return False
        finally:
            await client.aclose()
        return True


    async def async_get_customer(self):
        """Retrieves the customer information associated with the username logged into the API"""
        res = await self._async_get("api/usdm/v1/user/profile")
        json_result = res.json()

        self._customer_id = json_result['customerID']
        return json_result

    async def async_get_devices(self):
        """Gets a list of the Keurig devices associated with the logged in account"""
        # If we don't already have the customer details, get it
        if self._customer_id is None:
            await self.async_get_customer()
        res = await self._async_get("api/alcm/v1/devices?customerId="+ self._customer_id)
        json_result = res.json()

        self._devices = []
        for device in json_result['devices']:
            self._devices.append(KeurigDevice(self, device['id'], device['serialNumber'], device['model'], device['registration']['name']))

        return self._devices

    async def async_add_favorite(self, name: str, size: Size, temperature: Temperature, intensity: Intensity):
        """Add a favorite"""
        await self._async_post("api/usdm/v1/presets", data={'name': name, 'size': int(size), 'temperature': int(temperature), 
            'flowRate': int(intensity), 'brewMode': FAVORITE_BREW_MODE, 'deviceModel': FAVORITE_MODEL_NAME})

    async def async_update_favorite(self, id: str, name: str, size: Size, temperature: Temperature, intensity: Intensity):
        """Update a favorite"""
        await self._async_put("api/usdm/v1/presets/" + id, data={'name': name, 'size': int(size), 'temperature': int(temperature), 
            'flowRate': int(intensity), 'brewMode': FAVORITE_BREW_MODE, 'deviceModel': FAVORITE_MODEL_NAME})

    async def async_get_favorites(self):
        """Retrieves the list of favorites from the API"""
        res = await self._async_get("api/usdm/v1/presets")
        json_result = res.json()

        return json_result

    async def async_delete_favorite(self, favorite_id: str):
        """Delete a favorite"""
        await self._async_delete("api/usdm/v1/presets/" + favorite_id)

    async def async_connect(self):
        """Establishes a connection to the SignalR server to receive real-time push notifications."""

        # We need to do this to get the URL
        await self._async_get_signalr_access_token()
        
        hub_connection = HubConnectionBuilder()\
            .with_url(self._signalr_url, options={
                "access_token_factory": self._get_signalr_access_token
            })\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            }).build()
        hub_connection.on("appliance-notifications",self._receive_signalr)
        hub_connection.start()
        return True

    def connect(self):
        """Establishes a connection to the SignalR server to receive real-time push notifications."""

        # We need to do this to get the URL
        self._get_signalr_access_token()
        
        hub_connection = HubConnectionBuilder()\
            .with_url(self._signalr_url, options={
                "access_token_factory": self._get_signalr_access_token
            })\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            }).build()
        hub_connection.on("appliance-notifications",self._receive_signalr)
        hub_connection.start()
        return True

    async def _async_get_signalr_access_token(self):
        """Gets the SignalR URL and access token asynchronously"""
        res = await self._async_get("api/clnt/v1/signalr/negotiate")
        json_result = res.json()
        if "accessToken" in json_result.keys():
            self._signalr_access_token = json_result['accessToken']
        else:
            self._signalr_access_token = json_result['AccessToken']
        if "url" in json_result.keys():
            self._signalr_url = json_result['url']
        else:
            self._signalr_url = json_result['Url']
        self._signalr_url = self._signalr_url.replace("https://", "wss://")
        return self._signalr_access_token

    def _get_signalr_access_token(self):
        """Gets the SignalR URL and access token synchronously"""
        
        res = self._get("api/clnt/v1/signalr/negotiate")
        json_result = res.json()
        if "accessToken" in json_result.keys():
            self._signalr_access_token = json_result['accessToken']
        else:
            self._signalr_access_token = json_result['AccessToken']
        if "url" in json_result.keys():
            self._signalr_url = json_result['url']
        else:
            self._signalr_url = json_result['Url']
        self._signalr_url = self._signalr_url.replace("https://", "wss://")
        return self._signalr_access_token

    def _receive_signalr(self, args):
        """Handle processing a SignalR message"""
        if args is not None and len(args)>0:
            msg = args[0]
            device_id = msg['deviceId']
            body = msg['body']

            #It will be immediately followed by a BrewStateChange so no need to trigger two updates
            if msg['eventType'] == 'ApplianceStateChange' and body['current'] == 'BREW':
                return

            # Find the matching device and update its data
            device = next((device for device in self._devices if device.id == device_id))
            if device is not None:
                device._update_properties()
   
    def _get_headers(self):
        """Gets the default set of headers to pass to requests."""
        headers = {
            'User-Agent': HEADER_USER_AGENT,
            'Ocp-Apim-Subscription-Key': HEADER_OCP_SUBSCRIPTION_KEY,
            'Content-Type': 'application/json',     
            'reqId': str(uuid.uuid4())    
        }
        if self._access_token is not None:
            headers['Authorization'] = 'Bearer ' + self._access_token

        return headers

    def _post(self,
            request: str,
            content: Optional[bytes] = None,
            data: Optional[Dict] = None,
            headers: Optional[Dict] = None) -> httpx.Response:

        """Call POST endpoint of Keurig API synchronously."""
        
        endpoint = f"{API_URL}{request}"

        if self._token_expires_at <= time.time() and self._token_expires_at is not None:
            self._refresh_token()

        client = httpx.Client()

        try:
            client.headers = self._get_headers()
            client.headers.update(headers)

            res = client.post(endpoint
                , content=content, json=data, timeout=self.timeout)
            if res.status_code == 401:
                self._refresh_token()
                client.headers = self._get_headers()
                client.headers.update(headers)

                res = client.post(endpoint
                    , content=content, json=data, timeout=self.timeout)
            res.raise_for_status()
        finally:
            client.close()

        return res

    async def _async_post(
            self,
            request: str,
            content: Optional[bytes] = None,
            data: Optional[Dict] = None,
            headers: Optional[Dict] = None) -> httpx.Response:
        """Call POST endpoint of Keurig API asynchronously."""
        
        endpoint = f"{API_URL}{request}"

        if self._token_expires_at <= time.time() and self._token_expires_at is not None:
            await self._async_refresh_token()

        client = httpx.AsyncClient()

        try:
            client.headers = self._get_headers()
            client.headers.update(headers)

            res = await client.post(endpoint
                , content=content, json=data, timeout=self.timeout)
            if res.status_code == 401:
                await self._async_refresh_token()
                client.headers = self._get_headers()
                client.headers.update(headers)

                res = await client.post(endpoint
                    , content=content, json=data, timeout=self.timeout)
            res.raise_for_status()
        finally:
            await client.aclose()

    async def _async_delete(
            self,
            request: str,
            headers: Optional[Dict] = None) -> httpx.Response:
        """Call DELETE endpoint of Keurig API asynchronously."""
        
        endpoint = f"{API_URL}{request}"

        if self._token_expires_at <= time.time() and self._token_expires_at is not None:
            await self._async_refresh_token()

        client = httpx.AsyncClient()

        try:
            client.headers = self._get_headers()
            client.headers.update(headers)

            res = await client.delete(endpoint, timeout=self.timeout)
            if res.status_code == 401:
                await self._async_refresh_token()
                client.headers = self._get_headers()
                client.headers.update(headers)

                res = await client.delete(endpoint, timeout=self.timeout)
            res.raise_for_status()
        finally:
            await client.aclose()

        return res

    async def _async_put(
            self,
            request: str,
            content: Optional[bytes] = None,
            data: Optional[Dict] = None,
            headers: Optional[Dict] = None) -> httpx.Response:
        """Call PUT endpoint of Keurig API asynchronously."""
        
        endpoint = f"{API_URL}{request}"

        if self._token_expires_at <= time.time() and self._token_expires_at is not None:
            await self._async_refresh_token()

        client = httpx.AsyncClient()

        try:
            client.headers = self._get_headers()
            client.headers.update(headers)

            res = await client.put(endpoint
                , content=content, json=data, timeout=self.timeout)
            if res.status_code == 401:
                await self._async_refresh_token()
                client.headers = self._get_headers()
                client.headers.update(headers)

                res = await client.put(endpoint
                    , content=content, json=data, timeout=self.timeout)
            res.raise_for_status()
        finally:
            await client.aclose()

        return res

    def _get(
            self,
            request: str) -> httpx.Response:
        """Call GET endpoint of Keurig API synchronously."""
        
        endpoint = f"{API_URL}{request}"

        if self._token_expires_at <= time.time() and self._token_expires_at is not None:
            self._refresh_token()


        client = httpx.Client()
        client.headers = self._get_headers()
        try:
            res = client.get(endpoint, timeout=self.timeout)
            if res.status_code == 401:
                self._async_refresh_token()
                client.headers = self._get_headers()
                res = client.get(endpoint, timeout=self.timeout)
            res.raise_for_status()
        finally:
            client.close()

        return res

    async def _async_get(
        self,
        request: str) -> httpx.Response:
        """Call GET endpoint of Keurig API asynchronously."""
        
        endpoint = f"{API_URL}{request}"

        if self._token_expires_at <= time.time() and self._token_expires_at is not None:
            await self._async_refresh_token()


        client = httpx.AsyncClient()
        client.headers = self._get_headers()
        try:
            res = await client.get(endpoint, timeout=self.timeout)
            if res.status_code == 401:
                await self._async_refresh_token()
                client.headers = self._get_headers()
                res = await client.get(endpoint, timeout=self.timeout)
            res.raise_for_status()
        finally:
            await client.aclose()

        return res

    async def _async_refresh_token(self):
        """Retrieve a new access token asynchronously using a refresh_token"""

        data = {'grant_type': 'refresh_token', 'client_id': CLIENT_ID, 'refresh_token': self._refresh_token}

        client = httpx.AsyncClient()
        try:
            client.headers = self._get_headers()
            client.headers.update({'Accept-Encoding': 'identity'})

            endpoint = f"{API_URL}api/v2/oauth/token"
            res = await client.post(endpoint, json=data, timeout=self.timeout)
            res.raise_for_status()

            json_result = res.json()
            self._access_token = json_result['access_token']
            self._token_expires_at = time.time() + json_result['expires_in'] - 120
            self._refresh_token = json_result['refresh_token']
        except:
            return False
        finally:
            await client.aclose()

        return True

    def _refresh_token(self):
        """Retrieve a new access token synchronously using a refresh_token"""

        data = {'grant_type': 'refresh_token', 'client_id': CLIENT_ID, 'refresh_token': self._refresh_token}

        client = httpx.Client()
        try:
            client.headers = self._get_headers()
            client.headers.update({'Accept-Encoding': 'identity'})

            endpoint = f"{API_URL}api/v2/oauth/token"
            res = client.post(endpoint, json=data, timeout=self.timeout)
            res.raise_for_status()

            json_result = res.json()
            self._access_token = json_result['access_token']
            self._token_expires_at = time.time() + json_result['expires_in'] - 120
            self._refresh_token = json_result['refresh_token']
        except:
            return False
        finally:
            client.close()

        return True

class KeurigDevice:
    def __init__(self, api: KeurigApi, id, serial, model, name):
        self._callbacks = []
        self._api = api
        self._name = name
        self._id = id
        self._serial = serial
        self._model = model
        self._sw_version = None
        self._appliance_status = None
        self._brewer_status = None
        self._pod_status = None

    @property
    def id(self):
        """Get the device id"""
        return self._id

    @property
    def name(self):
        """Get the device name"""
        return self._name

    @property
    def serial(self):
        """Get the device serial number"""
        return self._serial

    @property
    def model(self):
        """Get the device model"""
        return self._model

    @property
    def sw_version(self):
        """Get the device firmware version"""
        return self._sw_version

    @property
    def appliance_status(self):
        """Get the device appliance status"""
        return self._appliance_status

    @property
    def brewer_status(self):
        """Get the device brewer status"""
        return self._brewer_status

    @property
    def brewer_error(self):
        """Get the device brewer error if in an error state"""
        return self._brewer_error

    @property
    def pod_status(self):
        """Get the device pod status"""
        return self._pod_status

    async def power_on(self):
        """Turn the device on"""
        await self._api._async_post("api/acsm/v1/devices/"+self._id+"/commands", data={'command_name': COMMAND_NAME_ON})
        return True

    async def power_off(self):
        """Turn the device off"""
        await self._api._async_post("api/acsm/v1/devices/"+self._id+"/commands", data={'command_name': COMMAND_NAME_OFF})
        return True

    async def hot_water(self, size: Size, temp: Temperature):
        """Brew hot water at the specified size and temperature"""
        await self._async_update_properties()
        # Must be ready, and empty
        if self._brewer_status != BREWER_STATUS_READY or self._pod_status != POD_STATUS_EMPTY:
            return False

        await self._api._async_post("api/acsm/v1/devices/"+self._id+"/commands", data={'command_name': COMMAND_NAME_BREW, 'params': 
        {
            'size': size,
            'brew_type': BREW_HOT_WATER,
            'flow_rate': Intensity.Balanced,
            'temp': temp,
            'enhanced': True,
            'category': BREW_CATEGORY_WATER
        }})
        return True

    async def brew_hot(self, size: Size, temp: Temperature, intensity: Intensity):
        """Brew a hot drink at the specified size, temperature, and intensity"""

        await self._async_update_properties()
        # Must be ready, and not empty
        if self._brewer_status != BREWER_STATUS_READY or self._pod_status == POD_STATUS_EMPTY:
            return False

        await self._api._async_post("api/acsm/v1/devices/"+self._id+"/commands", data={'command_name': COMMAND_NAME_BREW, 'params': 
        {
            'size': size,
            'brew_type': BREW_COFFEE,
            'flow_rate': intensity,
            'temp': temp,
            'enhanced': True,
            'category': BREW_CATEGORY_CUSTOM
        }})
        return True

    async def brew_iced(self):
        """Brew an iced drink"""

        await self._async_update_properties()
        # Must be ready, and not empty
        if self._brewer_status != BREWER_STATUS_READY or self._pod_status == POD_STATUS_EMPTY:
            return False

        await self._api._async_post("api/acsm/v1/devices/"+self._id+"/commands", data={'command_name': COMMAND_NAME_BREW, 'params': 
        {
            'size': 6,
            'brew_type': BREW_OVER_ICE,
            'flow_rate': Intensity.BREW_INTENSE,
            'temp': 201,
            'enhanced': True,
            'category': BREW_CATEGORY_ICED
        }})
        return True

    async def brew_recommendation(self, size: Size):
        """Brew a drink at the recommended settings for the k-cup at the specified size"""
        json_result = await self._async_update_properties()
        # Must be ready, and not empty
        if self._brewer_status != BREWER_STATUS_READY or self._pod_status == POD_STATUS_EMPTY:
            return False
        # get recommended brew settings based on size
        pod_state = next((item for item in json_result if item['name'] == NODE_POD_STATE))
        recipes = pod_state['value']['pod_details']['recipes']
        recipe = next((recipe for recipe in recipes if recipe['size'] == size))
        temp = recipe['temp']
        flow_rate = recipe['flow_rate']
        
        await self._api._async_post("api/acsm/v1/devices/"+self._id+"/commands", data={'command_name': COMMAND_NAME_BREW, 'params': 
        {
            'size': size,
            'brew_type': BREW_COFFEE,
            'flow_rate': flow_rate,
            'temp': temp,
            'enhanced': True,
            'category': BREW_CATEGORY_RECOMMENDED
        }})

    async def brew_favorite(self, favorite_id: str):
        """Brew the specified favorite setting"""
        await self._async_update_properties()
        # Must be ready, and not empty
        if self._brewer_status != BREWER_STATUS_READY or self._pod_status == POD_STATUS_EMPTY:
            return False

        # get favorite
        favorites = await self._api.async_get_favorites()

        favorite = next((fav for fav in favorites if fav['id'] == favorite_id))

        if favorite is not None:
            size = favorite['size']
            flow_rate = favorite['flowRate']
            temp = favorite['temperature']

            # do brew
            await self._api._async_post("api/acsm/v1/devices/"+self._id+"/commands", data={'command_name': COMMAND_NAME_BREW, 'params': 
            {
                'size': size,
                'brew_type': BREW_COFFEE,
                 'flow_rate': flow_rate,
                 'temp': temp,
                'enhanced': True,
                'category': BREW_CATEGORY_FAVORITE
            }})

    async def cancel_brew(self):
        """Cancel the current brewing."""
        try:
            await self._api._async_post("api/acsm/v1/devices/"+self._id+"/commands", data={'command_name': COMMAND_NAME_CANCEL_BREW})
        except:
            return False
        return True

    def register_callback(self, callback=lambda *args, **kwargs: None):
        """Adds a callback to be triggered when an event is received."""
        self._callbacks.append(callback)

    def unregister_callback(self, callback=lambda *args, **kwargs: None):
        """Removes a callback that gets triggered when an event is received."""
        self._callbacks.remove(callback)

    async def async_update(self):
        """Update the device properties"""
        await self._async_update_properties()

    async def _async_update_properties(self): 
        """Asynchronously update the device properties"""
        try:
            res = await self._api._async_get("api/acsm/v1/devices/"+self._id+"/properties")
            json_result = res.json()

            appliance_state = next((item for item in json_result if item['name'] == NODE_APPLIANCE_STATE))
            brew_state = next((item for item in json_result if item['name'] == NODE_BREW_STATE))
            pod_state = next((item for item in json_result if item['name'] == NODE_POD_STATE))
            sw_info = next((item for item in json_result if item['name'] == NODE_SW_INFO))

            self._appliance_status = appliance_state['value']['current']
            self._brewer_status = brew_state['value']['current']
            self._pod_status = pod_state['value']['pm_content']
            self._sw_version = sw_info['value']['appliance']
            if brew_state['value']['lock_cause'] is not None:
                self._brewer_error = brew_state['value']['lock_cause']
            elif brew_state['value']['error'] is not None:
                self._brewer_error = brew_state['value']['error']
            else:
                self._brewer_error = None

            for callback in self._callbacks:
                try:
                    callback(self)
                except:
                    pass
            return json_result
        except Exception as err:
            _LOGGER.error(err)

    def _update_properties(self):
        """Synchronously update the device properties"""
        try:
            res = self._api._get("api/acsm/v1/devices/"+self._id+"/properties")
            json_result = res.json()

            appliance_state = next((item for item in json_result if item['name'] == NODE_APPLIANCE_STATE))
            brew_state = next((item for item in json_result if item['name'] == NODE_BREW_STATE))
            pod_state = next((item for item in json_result if item['name'] == NODE_POD_STATE))

            self._appliance_status = appliance_state['value']['current']
            self._brewer_status = brew_state['value']['current']
            self._pod_status = pod_state['value']['pm_content']
            if brew_state['value']['lock_cause'] is not None:
                self._brewer_error = brew_state['value']['lock_cause']
            elif brew_state['value']['error'] is not None:
                self._brewer_error = brew_state['value']['error']
            else:
                self._brewer_error = None

            for callback in self._callbacks:
                try:
                    callback(self)
                except:
                    pass
            return json_result
        except Exception as err:
            _LOGGER.error(err)