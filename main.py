import asyncio
from pykeurig.const import CLIENT_ID
from pykeurig.keurigapi import KeurigApi


api = KeurigApi()

def _msg_received(dev):
    print('msg received')
    print(dev.appliance_status)
    print(dev.brewer_status)
    print(dev.brewer_error)
    print(dev.pod_status)

async def run_async():
    print(await api.login("smarthome.logins+keurig@gmail.com", "Feargo121$"))
    print(await api.get_customer())
    devices = await api.get_devices()

    device = devices[0]
    device.register_callback(_msg_received)
    print (await api.async_connect())
    await asyncio.sleep(10)
    print("power on")
    await device.power_on()
    
    await asyncio.sleep(100)
    


loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(run_async())
loop.close()

