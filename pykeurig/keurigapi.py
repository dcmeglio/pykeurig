import asyncio
import json
import logging
import time

from typing import Callable, Dict, Hashable, Optional, Tuple
from wsgiref import headers

import httpx

from signalrcore.hub_connection_builder import HubConnectionBuilder

from pykeurig.const import API_URL, BREW_CATEGORY_CUSTOM, BREW_CATEGORY_ICED, BREW_CATEGORY_WATER, BREW_COFFEE, BREW_HOT_WATER, BREW_OVER_ICE, BREWER_STATUS_NOT_READY, BREWER_STATUS_READY, CLIENT_ID, COMMAND_NAME_BREW, COMMAND_NAME_CANCEL_BREW, COMMAND_NAME_OFF, COMMAND_NAME_ON, HEADER_OCP_SUBSCRIPTION_KEY, HEADER_USER_AGENT, NODE_APPLIANCE_STATE, NODE_BREW_STATE, NODE_POD_STATE, POD_STATUS_EMPTY, STATUS_OFF, STATUS_ON, Intensity, Size, Temperature


_LOGGER = logging.getLogger(__name__)


def get_default_async_client() -> httpx.AsyncClient:
    """Get the default httpx.AsyncClient."""
    return httpx.AsyncClient()

class KeurigApi:
    timeout = 10
    def __init__(self):
        self._access_token = None
        self._token_expires_at = None
        self._refresh_token = None

    async def login(self, email, password):
        try:
            data = {'grant_type': 'password', 'client_id': CLIENT_ID, 'username': email, 'password': password}
            client = get_default_async_client()
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


    async def get_customer(self):
        res = await self._async_get("api/usdm/v1/user/profile")
        json_result = res.json()

        self._customer_id = json_result['customerID']
        return json_result

    async def get_devices(self):
        res = await self._async_get("api/alcm/v1/devices?customerId="+ self._customer_id)
        json_result = res.json()

        self._devices = []
        for device in json_result['devices']:
            self._devices.append(KeurigDevice(self, device['id'], device['serialNumber'], device['model'], device['registration']['name']))

        return self._devices


    async def async_connect(self):
        res = await self._async_get("api/clnt/v1/signalr/negotiate")
        json_result = res.json()
        self._signalr_access_token = json_result['accessToken']
        self._signalr_url = json_result['url']
    #    self._signalr_url = 'https://kcbu-signalr-prod.service.signalr.net/client/?hub=customer'
     #   self._signalr_access_token = 'eyJhbGciOiJIUzI1NiIsImtpZCI6Ii03ODE3NTkwMDYiLCJ0eXAiOiJKV1QifQ.eyJhc3JzLnMudWlkIjoiMDAwMDMxODM4MjM0IiwiYXNycy5zLmF1dCI6IldlYkpvYnNBdXRoTGV2ZWwiLCJuYmYiOjE2NjcwOTA4MjUsImV4cCI6MTY2NzA5NDQyNSwiaWF0IjoxNjY3MDkwODI1LCJhdWQiOiJodHRwczovL2tjYnUtc2lnbmFsci1wcm9kLnNlcnZpY2Uuc2lnbmFsci5uZXQvY2xpZW50Lz9odWI9Y3VzdG9tZXIifQ.au8GqtDwD04CKk1PNEiqIQnVzx8tf1CoYUR91W901Os'

        self._signalr_url = self._signalr_url.replace("https://", "wss://")
        hub_connection = HubConnectionBuilder()\
            .with_url(self._signalr_url, options={
                "headers":{
                    "Authorization": "Bearer " + self._signalr_access_token
            }})\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            }).build()

        #hub_connection.on_open(lambda: print("connection opened and handshake received ready to send messages"))
        #hub_connection.on_close(lambda: print("connection closed"))
        hub_connection.on("appliance-notifications",self._receive_signalr)
        hub_connection.start()
        return True

    def _receive_signalr(self, args):
        if args is not None and len(args)>0:
            msg = args[0]
            device_id = msg['deviceId']
            body = msg['body']
            device = next((device for device in self._devices if device.id == device_id))
            if device is not None:
                device._update_properties()
                """
                if msg['eventType'] == "ApplianceStateChange":
                    device.update_states(appliance_status = body['current'])
                    if device._appliance_status == STATUS_ON:
                        device._update_properties()
                elif msg['eventType'] == "BrewStateChange":
                    brewer_status = body['current']
                    brewer_error = None
                    if body['current'] == BREWER_STATUS_NOT_READY:
                        brewer_error = body['lock_cause']
                    device.update_states(brewer_status=brewer_status, brewer_error=brewer_error)
                elif msg['eventType'] == "PodRecognitionEvent":
                    # We don't currently do anything for a pod recognition event
                    pass
                else:
                    _LOGGER.warn("Unknown event " + msg['eventType'])
                """
   

    def _get_headers(self):
        headers = {
            'User-Agent': HEADER_USER_AGENT,
            'Ocp-Apim-Subscription-Key': HEADER_OCP_SUBSCRIPTION_KEY,
            'Content-Type': 'application/json'
        }
        if self._access_token is not None:
            headers['Authorization'] = 'Bearer ' + self._access_token

        return headers

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

        client = get_default_async_client()

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

        return res

    async def _async_get(
            self,
            request: str) -> httpx.Response:
        
        endpoint = f"{API_URL}{request}"

        if self._token_expires_at <= time.time() and self._token_expires_at is not None:
            await self._async_refresh_token()


        client = get_default_async_client()
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
        data = {'grant_type': 'refresh_token', 'client_id': CLIENT_ID, 'refresh_token': self._refresh_token}

        client = get_default_async_client()
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

class KeurigDevice:
    def __init__(self, api: KeurigApi, id, serial, model, name):
        self._callbacks = []
        self._api = api
        self._name = name
        self._id = id
        self._serial = serial
        self._model = model
        self._appliance_status = None
        self._brewer_status = None
        self._pod_status = None

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def serial(self):
        return self._serial

    @property
    def model(self):
        return self._model

    @property
    def appliance_status(self):
        return self._appliance_status

    @property
    def brewer_status(self):
        return self._brewer_status

    @property
    def brewer_error(self):
        return self._brewer_error

    @property
    def pod_status(self):
        return self._pod_status

    async def power_on(self):
        await self._api._async_post("api/acsm/v1/devices/"+self._id+"/commands", data={'command_name': COMMAND_NAME_ON})
        return True

    async def power_off(self):
        await self._api._async_post("api/acsm/v1/devices/"+self._id+"/commands", data={'command_name': COMMAND_NAME_OFF})
        return True

    async def _async_update_properties(self):
        try:
            res = await self._api._async_get("api/acsm/v1/devices/"+self._id+"/properties")
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
        except:
            pass

    def _update_properties(self):
        # Run async function in own event loop
        loop = asyncio.new_event_loop()

        try:
            return loop.run_until_complete(self._async_update_properties())
        finally:
            loop.close()

    async def hot_water(self, size: Size, temp: Temperature):
        await self._async_update_properties()
        # Must be on, ready, and empty
        if self._appliance_status != STATUS_ON or self._brewer_status != BREWER_STATUS_READY or self._pod_status != POD_STATUS_EMPTY:
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
        await self._async_properties()
        # Must be on, ready, and not empty
        if self._appliance_status != STATUS_ON or self._brewer_status != BREWER_STATUS_READY or self._pod_status == POD_STATUS_EMPTY:
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
        await self._async_properties()
        # Must be on, ready, and not empty
        if self._appliance_status != STATUS_ON or self._brewer_status != BREWER_STATUS_READY or self._pod_status == POD_STATUS_EMPTY:
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

    async def brew_recommendation(self):
        pass

    async def brew_favorite(self):
        pass

    async def cancel_brew(self):
        await self._api._async_post("api/acsm/v1/devices/"+self._id+"/commands", data={'command_name': COMMAND_NAME_CANCEL_BREW})
        return True

#{"command_name":"brew","params":{"size":8,"brew_type":"HOT_WATER","flow_rate":4435,"temp":194,"enhanced":true,"category":"WATER"}}
    def update_states(self, appliance_status = None, brewer_status = None, brewer_error = None, pod_status = None):
        if appliance_status is not None:
            self._appliance_status = appliance_status
        if brewer_status is not None:
            self._brewer_status = brewer_status
        self._brewer_error = brewer_error
        if pod_status is not None:
            self._pod_status = pod_status
    

    def register_callback(self, callback=lambda *args, **kwargs: None):
        """Adds a callback to be triggered when an event is received."""
        self._callbacks.append(callback)

    def unregister_callback(self, callback=lambda *args, **kwargs: None):
        """Removes a callback that gets triggered when an event is received."""
        self._callbacks.remove(callback)





#{'change_cause': 'REMOTE_IDLE_REQUEST', 'current': 'IDLE', 'fault_cause': '', 'info': '', 'lock_cause': '', 'timestamp': 1667091776}
#{"brew_error":"","current":"BREW_SUCCESSFUL","lock_cause":"","recipe":{"brew_type":"NORMAL","category":"DEFAULT","enhanced":true,"flow_rate":4435,"size":12,"temp":194},"timestamp":1667051726,"brewer_error":""}
