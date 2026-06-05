import logging
import asyncio
import hashlib
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class CastDevice:
    def __init__(self, device_id: str, name: str, device_type: str, address: str, port: int = 0):
        self.id = device_id
        self.name = name
        self.type = device_type
        self.address = address
        self.port = port

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "address": self.address,
            "port": self.port,
        }


class CastManager:
    def __init__(self):
        self._devices: list[CastDevice] = []
        self._last_scan_time = 0
        self._cache_ttl = 60
        self._chromecast_instances: dict[str, Any] = {}

    async def discover_devices(self) -> list[dict]:
        import time
        now = time.time()
        if now - self._last_scan_time < self._cache_ttl and self._devices:
            return [d.to_dict() for d in self._devices]

        devices = []

        dlna_devices = await self._discover_dlna()
        devices.extend(dlna_devices)

        cc_devices = await self._discover_chromecast()
        devices.extend(cc_devices)

        self._devices = devices
        self._last_scan_time = now
        return [d.to_dict() for d in devices]

    async def _discover_dlna(self) -> list[CastDevice]:
        devices = []
        try:
            from async_upnp_client.search import async_search

            found_devices = []

            async def _callback(data):
                found_devices.append(data)

            await asyncio.wait_for(
                async_search(
                    _callback,
                    search_target="urn:schemas-upnp-org:device:MediaRenderer:1",
                    timeout=4,
                ),
                timeout=6,
            )
            for entry in found_devices:
                location = entry.get("location", "") or entry.get("LOCATION", "")
                name = entry.get("server", "") or entry.get("SERVER", location)
                device_id = hashlib.md5(location.encode()).hexdigest()[:12]
                host = entry.get("_host", "")
                devices.append(CastDevice(
                    device_id=f"dlna_{device_id}",
                    name=name,
                    device_type="dlna",
                    address=host or location,
                ))
        except ImportError:
            logger.debug("async-upnp-client not installed, DLNA discovery unavailable")
        except asyncio.TimeoutError:
            logger.debug("DLNA discovery timed out")
        except Exception as e:
            logger.debug(f"DLNA discovery: {e}")
        return devices

    async def _discover_chromecast(self) -> list[CastDevice]:
        devices = []
        try:
            import pychromecast

            def _scan():
                browser = pychromecast.CastBrowser(
                    pychromecast.SimpleCastListener(lambda uuid, name: None),
                    pychromecast.zeroconf.start_discovery(None),
                )
                browser.start_discovery()
                import time
                time.sleep(5)
                browser.stop_discovery()
                chromecasts = list(browser.devices.values())
                return chromecasts

            cast_infos = await asyncio.to_thread(_scan)
            for info in cast_infos:
                device_id = hashlib.md5(info.friendly_name.encode()).hexdigest()[:12]
                devices.append(CastDevice(
                    device_id=f"cc_{device_id}",
                    name=info.friendly_name,
                    device_type="chromecast",
                    address=str(info.host),
                    port=info.port,
                ))
        except ImportError:
            logger.debug("pychromecast not installed, Chromecast discovery unavailable")
        except Exception as e:
            logger.debug(f"Chromecast discovery: {e}")
        return devices

    async def cast_to_device(self, device_id: str, media_url: str, content_type: str = "video/mp4") -> bool:
        device = self._find_device(device_id)
        if not device:
            return False

        if device.type == "chromecast":
            return await self._cast_chromecast(device_id, media_url, content_type)
        elif device.type == "dlna":
            return await self._cast_dlna(device, media_url, content_type)
        return False

    async def _cast_chromecast(self, device_id: str, media_url: str, content_type: str) -> bool:
        try:
            import pychromecast
            cc = self._chromecast_instances.get(device_id)
            if not cc:
                return False

            cc.wait()
            mc = cc.media_controller
            mc.play_media(media_url, content_type)
            mc.block_until_active()
            return True
        except Exception as e:
            logger.error(f"Chromecast cast error: {e}")
            return False

    async def _cast_dlna(self, device: CastDevice, media_url: str, content_type: str) -> bool:
        try:
            from async_upnp_client.aiohttp import AiohttpRequester
            from async_upnp_client.client_factory import UpnpFactory
            from async_upnp_client.client import UpnpDevice

            requester = AiohttpRequester()
            factory = UpnpFactory(requester)
            upnp_device = await factory.async_create_device(f"http://{device.address}:{device.port}/description.xml")
            av_transport = upnp_device.service("urn:schemas-upnp-org:service:AVTransport:1")

            await av_transport.action("SetAVTransportURI").async_call(
                InstanceID=0,
                CurrentURI=media_url,
                CurrentURIMetaData="",
            )
            await av_transport.action("Play").async_call(InstanceID=0, Speed="1")
            return True
        except Exception as e:
            logger.error(f"DLNA cast error: {e}")
            return False

    async def control_device(self, device_id: str, action: str, **kwargs) -> bool:
        device = self._find_device(device_id)
        if not device:
            return False

        if device.type == "chromecast":
            return await self._control_chromecast(device_id, action, **kwargs)
        return False

    async def _control_chromecast(self, device_id: str, action: str, **kwargs) -> bool:
        try:
            cc = self._chromecast_instances.get(device_id)
            if not cc:
                return False
            mc = cc.media_controller
            if action == "pause":
                mc.pause()
            elif action == "play":
                mc.play()
            elif action == "stop":
                mc.stop()
            elif action == "seek":
                mc.seek(kwargs.get("position", 0))
            return True
        except Exception as e:
            logger.error(f"Chromecast control error: {e}")
            return False

    def _find_device(self, device_id: str) -> CastDevice | None:
        for d in self._devices:
            if d.id == device_id:
                return d
        return None

    async def get_device_status(self, device_id: str) -> dict | None:
        device = self._find_device(device_id)
        if not device:
            return None

        if device.type == "chromecast":
            cc = self._chromecast_instances.get(device_id)
            if cc and cc.media_controller.status:
                status = cc.media_controller.status
                return {
                    "device_id": device_id,
                    "state": str(status.player_state) if status.player_state else "UNKNOWN",
                    "current_time": status.current_time or 0,
                    "duration": status.duration or 0,
                    "title": status.title or "",
                }
        return {"device_id": device_id, "state": "UNKNOWN"}


cast_manager = CastManager()
