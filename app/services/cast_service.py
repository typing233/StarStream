import socket
import struct
import logging
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pychromecast
    CHROMECAST_AVAILABLE = True
except ImportError:
    CHROMECAST_AVAILABLE = False


class CastDevice:
    def __init__(self, device_id: str, name: str, device_type: str, address: str, port: int = 0):
        self.device_id = device_id
        self.name = name
        self.device_type = device_type
        self.address = address
        self.port = port


class CastService:
    def __init__(self):
        self._devices: dict[str, CastDevice] = {}
        self._chromecast_instances: dict[str, object] = {}
        self._dlna_state: dict[str, dict] = {}

    def discover(self, timeout: float = 5.0) -> list[dict]:
        devices = []
        devices.extend(self._discover_dlna(timeout))
        if CHROMECAST_AVAILABLE:
            devices.extend(self._discover_chromecast(timeout))
        return devices

    def _discover_dlna(self, timeout: float) -> list[dict]:
        found = []
        ssdp_request = (
            "M-SEARCH * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            "MAN: \"ssdp:discover\"\r\n"
            "MX: 3\r\n"
            "ST: urn:schemas-upnp-org:service:AVTransport:1\r\n"
            "\r\n"
        )
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(timeout)
            sock.sendto(ssdp_request.encode(), ("239.255.255.250", 1900))

            while True:
                try:
                    data, addr = sock.recvfrom(4096)
                    response = data.decode("utf-8", errors="ignore")
                    location = None
                    for line in response.split("\r\n"):
                        if line.lower().startswith("location:"):
                            location = line.split(":", 1)[1].strip()
                            break
                    if location:
                        device = self._parse_dlna_device(location, addr[0])
                        if device:
                            found.append(device)
                except socket.timeout:
                    break
            sock.close()
        except Exception as e:
            logger.debug(f"DLNA discovery error: {e}")

        return found

    def _parse_dlna_device(self, location: str, ip: str) -> Optional[dict]:
        try:
            with urllib.request.urlopen(location, timeout=3) as resp:
                xml_data = resp.read()
            root = ET.fromstring(xml_data)
            ns = {"d": "urn:schemas-upnp-org:device-1-0"}
            device_el = root.find(".//d:device", ns)
            if device_el is None:
                return None
            name = device_el.findtext("d:friendlyName", "Unknown DLNA", ns)
            udn = device_el.findtext("d:UDN", "", ns)
            device_id = f"dlna_{udn.replace('uuid:', '')}" if udn else f"dlna_{ip}"

            dev = CastDevice(device_id=device_id, name=name, device_type="dlna", address=ip)
            self._devices[device_id] = dev

            control_url = None
            for service in device_el.findall(".//d:service", ns):
                service_type = service.findtext("d:serviceType", "", ns)
                if "AVTransport" in service_type:
                    control_url = service.findtext("d:controlURL", "", ns)
                    break

            if control_url:
                base = location.rsplit("/", 1)[0]
                if not control_url.startswith("http"):
                    control_url = base + "/" + control_url.lstrip("/")
                self._dlna_state[device_id] = {"control_url": control_url, "status": "idle"}

            return {"id": device_id, "name": name, "type": "dlna", "address": ip}
        except Exception as e:
            logger.debug(f"Error parsing DLNA device at {location}: {e}")
            return None

    def _discover_chromecast(self, timeout: float) -> list[dict]:
        found = []
        try:
            chromecasts, browser = pychromecast.get_chromecasts(timeout=timeout)
            for cc in chromecasts:
                device_id = f"cc_{cc.uuid}"
                dev = CastDevice(
                    device_id=device_id, name=cc.cast_info.friendly_name,
                    device_type="chromecast", address=str(cc.cast_info.host), port=cc.cast_info.port,
                )
                self._devices[device_id] = dev
                self._chromecast_instances[device_id] = cc
                found.append({"id": device_id, "name": dev.name, "type": "chromecast", "address": dev.address})
            browser.stop_discovery()
        except Exception as e:
            logger.debug(f"Chromecast discovery error: {e}")
        return found

    def play(self, device_id: str, stream_url: str, content_type: str = "video/mp4", title: str = "") -> bool:
        device = self._devices.get(device_id)
        if not device:
            return False

        if device.device_type == "dlna":
            return self._dlna_play(device_id, stream_url, content_type)
        elif device.device_type == "chromecast":
            return self._chromecast_play(device_id, stream_url, content_type, title)
        return False

    def pause(self, device_id: str) -> bool:
        device = self._devices.get(device_id)
        if not device:
            return False
        if device.device_type == "dlna":
            return self._dlna_command(device_id, "Pause")
        elif device.device_type == "chromecast":
            cc = self._chromecast_instances.get(device_id)
            if cc:
                cc.media_controller.pause()
                return True
        return False

    def stop(self, device_id: str) -> bool:
        device = self._devices.get(device_id)
        if not device:
            return False
        if device.device_type == "dlna":
            return self._dlna_command(device_id, "Stop")
        elif device.device_type == "chromecast":
            cc = self._chromecast_instances.get(device_id)
            if cc:
                cc.media_controller.stop()
                return True
        return False

    def status(self, device_id: str) -> dict:
        device = self._devices.get(device_id)
        if not device:
            return {"error": "Device not found"}
        if device.device_type == "chromecast":
            cc = self._chromecast_instances.get(device_id)
            if cc and cc.media_controller.status:
                ms = cc.media_controller.status
                return {
                    "device": device.name, "state": str(ms.player_state),
                    "position": ms.current_time, "duration": ms.duration,
                }
        elif device.device_type == "dlna":
            state = self._dlna_state.get(device_id, {})
            return {"device": device.name, "state": state.get("status", "unknown")}
        return {"device": device.name, "state": "unknown"}

    def _dlna_play(self, device_id: str, url: str, content_type: str) -> bool:
        state = self._dlna_state.get(device_id)
        if not state or "control_url" not in state:
            return False
        control_url = state["control_url"]

        soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <CurrentURI>{url}</CurrentURI>
      <CurrentURIMetaData></CurrentURIMetaData>
    </u:SetAVTransportURI>
  </s:Body>
</s:Envelope>"""

        try:
            req = urllib.request.Request(control_url, data=soap_body.encode(), method="POST")
            req.add_header("Content-Type", 'text/xml; charset="utf-8"')
            req.add_header("SOAPAction", '"urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI"')
            urllib.request.urlopen(req, timeout=5)

            play_body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <Speed>1</Speed>
    </u:Play>
  </s:Body>
</s:Envelope>"""
            req2 = urllib.request.Request(control_url, data=play_body.encode(), method="POST")
            req2.add_header("Content-Type", 'text/xml; charset="utf-8"')
            req2.add_header("SOAPAction", '"urn:schemas-upnp-org:service:AVTransport:1#Play"')
            urllib.request.urlopen(req2, timeout=5)

            state["status"] = "playing"
            return True
        except Exception as e:
            logger.error(f"DLNA play error: {e}")
            return False

    def _dlna_command(self, device_id: str, action: str) -> bool:
        state = self._dlna_state.get(device_id)
        if not state or "control_url" not in state:
            return False
        control_url = state["control_url"]

        soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:{action} xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
    </u:{action}>
  </s:Body>
</s:Envelope>"""

        try:
            req = urllib.request.Request(control_url, data=soap_body.encode(), method="POST")
            req.add_header("Content-Type", 'text/xml; charset="utf-8"')
            req.add_header("SOAPAction", f'"urn:schemas-upnp-org:service:AVTransport:1#{action}"')
            urllib.request.urlopen(req, timeout=5)
            state["status"] = action.lower()
            return True
        except Exception as e:
            logger.error(f"DLNA {action} error: {e}")
            return False

    def _chromecast_play(self, device_id: str, url: str, content_type: str, title: str) -> bool:
        cc = self._chromecast_instances.get(device_id)
        if not cc:
            return False
        try:
            cc.wait(timeout=5)
            mc = cc.media_controller
            mc.play_media(url, content_type, title=title)
            mc.block_until_active(timeout=10)
            return True
        except Exception as e:
            logger.error(f"Chromecast play error: {e}")
            return False


cast_service = CastService()
