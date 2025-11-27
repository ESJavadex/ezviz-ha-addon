#!/usr/bin/env python3
"""
EZVIZ Stream Capture - Standalone Package
Capture unencrypted video streams from EZVIZ cameras

No external dependencies except requests
"""

import requests
import socket
import struct
import hashlib
import base64
import json
import time
import re
from urllib.parse import urlencode

__version__ = "1.0.0"
__author__ = "EZVIZ-RE"

# ============================================================================
# CONFIGURATION
# ============================================================================

class EzvizConfig:
    """Configuration for EZVIZ connection"""

    # Region mappings
    REGIONS = {
        "Europe": "ieu",
        "Africa": "ieu",
        "Asia": "isgp",
        "NorthAmerica": "ius",
        "Oceania": "ius",
        "SouthAmerica": "isa",
    }

    # Protocol constants
    MSG_STREAMINFO_REQ = 0x13b
    MSG_STREAMINFO_RSP = 0x13c
    MSG_KEEPALIVE_REQ = 0x135

    CHANNEL_UNENC_MESSAGE = 0x00
    CHANNEL_UNENC_STREAM = 0x01
    CHANNEL_ENC_MESSAGE = 0x0a
    CHANNEL_ENC_STREAM = 0x0b

    MAGIC_BYTE = 0x24

    # API settings
    CLIENT_TYPE = 9  # PC/Studio
    CLIENT_NO = "shipin7"
    CLIENT_VERSION = "2,5,1,2109068"
    CUSTOM_NO = "1000001"
    APP_ID = "ys7"
    FEATURE_CODE = "00000000000000000000000000000000"


# ============================================================================
# PROTOBUF ENCODING
# ============================================================================

class ProtobufEncoder:
    """Manual Protobuf encoding for EZVIZ messages"""

    @staticmethod
    def encode_varint(value):
        """Encode integer as protobuf varint"""
        result = []
        while value > 0x7f:
            result.append((value & 0x7f) | 0x80)
            value >>= 7
        result.append(value & 0x7f)
        return bytes(result)

    @staticmethod
    def encode_string(field_number, value):
        """Encode string field (wire type 2)"""
        tag = (field_number << 3) | 2
        encoded_value = value.encode('utf-8')
        return (ProtobufEncoder.encode_varint(tag) +
                ProtobufEncoder.encode_varint(len(encoded_value)) +
                encoded_value)

    @staticmethod
    def encode_int32(field_number, value):
        """Encode int32 field (wire type 0)"""
        tag = (field_number << 3) | 0
        return ProtobufEncoder.encode_varint(tag) + ProtobufEncoder.encode_varint(value)

    @staticmethod
    def create_stream_info_req(stream_url, vtm_stream_key=""):
        """Create StreamInfoReq protobuf message"""
        message = b""
        message += ProtobufEncoder.encode_string(1, stream_url)
        if vtm_stream_key:
            message += ProtobufEncoder.encode_string(2, vtm_stream_key)
        message += ProtobufEncoder.encode_string(3, "v3.6.3.20221124")
        message += ProtobufEncoder.encode_int32(4, 0)
        message += ProtobufEncoder.encode_string(6, "v3.6.3.20221124")
        return message


# ============================================================================
# VTM PACKET FORMAT
# ============================================================================

class VTMPacket:
    """VTM packet encoder/decoder"""

    @staticmethod
    def encode(data, message_code, channel=EzvizConfig.CHANNEL_UNENC_MESSAGE, sequence=0):
        """
        Encode VTM packet with 8-byte header

        Header format:
        [0] Magic: 0x24
        [1] Channel: 0x00 (unenc msg) / 0x01 (unenc stream)
        [2-3] Length: uint16 big-endian
        [4-5] Sequence: uint16 big-endian
        [6-7] Message Code: uint16 big-endian
        """
        header = struct.pack(
            '>BBHHH',
            EzvizConfig.MAGIC_BYTE,
            channel,
            len(data),
            sequence,
            message_code
        )
        return header + data

    @staticmethod
    def decode_header(header):
        """Decode VTM packet header"""
        if len(header) != 8:
            raise ValueError(f"Invalid header length: {len(header)}")

        magic, channel, length, sequence, msg_code = struct.unpack('>BBHHH', header)

        if magic != EzvizConfig.MAGIC_BYTE:
            raise ValueError(f"Invalid magic byte: 0x{magic:02x}")

        return {
            "magic": magic,
            "channel": channel,
            "length": length,
            "sequence": sequence,
            "message_code": msg_code,
        }


# ============================================================================
# EZVIZ API CLIENT
# ============================================================================

class EzvizAPI:
    """EZVIZ API client for authentication and device management"""

    def __init__(self, email, password, region="Europe"):
        self.email = email
        self.password = self._md5(password)
        self.region = region
        self.region_code = EzvizConfig.REGIONS.get(region, "ieu")
        self.api_url = f"https://api{self.region_code}.ezvizlife.com"
        self.auth_url = None
        self.session_id = None

    @staticmethod
    def _md5(text):
        """Generate MD5 hash"""
        return hashlib.md5(text.encode()).hexdigest()

    def _get_headers(self, include_session=False):
        """Build API request headers"""
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "featureCode": EzvizConfig.FEATURE_CODE,
            "clientType": str(EzvizConfig.CLIENT_TYPE),
            "clientVersion": EzvizConfig.CLIENT_VERSION,
            "customNo": EzvizConfig.CUSTOM_NO,
            "clientNo": EzvizConfig.CLIENT_NO,
            "appId": EzvizConfig.APP_ID,
        }
        if include_session and self.session_id:
            headers["sessionId"] = self.session_id
        return headers

    def login(self):
        """Login to EZVIZ API"""
        endpoint = "/v3/users/login/v5"
        data = {
            "account": self.email,
            "password": self.password,
            "featureCode": EzvizConfig.FEATURE_CODE,
            "cuName": base64.b64encode(b"EZVIZ-RE").decode(),
        }

        response = requests.post(
            f"{self.api_url}{endpoint}",
            data=urlencode(data),
            headers=self._get_headers()
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("meta", {}).get("code") == 200:
                self.session_id = result["loginSession"]["sessionId"]
                return True

        return False

    def get_server_info(self):
        """Get server information (AUTH_URL)"""
        endpoint = "/api/server/info/get"
        data = {
            "sessionId": self.session_id,
            "clientType": str(EzvizConfig.CLIENT_TYPE),
        }

        response = requests.post(
            f"{self.api_url}{endpoint}",
            data=urlencode(data),
            headers=self._get_headers(include_session=True)
        )

        if response.status_code == 200:
            result = response.json()
            self.auth_url = result["serverResp"]["authAddr"]
            return result

        return None

    def get_devices(self):
        """Get device list"""
        endpoint = "/v3/userdevices/v1/resources/pagelist"
        params = {
            "sessionId": self.session_id,
            "clientType": str(EzvizConfig.CLIENT_TYPE),
            "clientNo": EzvizConfig.CLIENT_NO,
            "clientVersion": EzvizConfig.CLIENT_VERSION,
            "groupId": "-1",
            "limit": "50",
            "offset": "0",
            "filter": "VTM"
        }

        response = requests.get(
            f"{self.api_url}{endpoint}?{urlencode(params)}",
            headers=self._get_headers(include_session=True)
        )

        if response.status_code == 200:
            return response.json()

        return None

    def get_vtdu_tokens(self):
        """Get VTDU streaming tokens"""
        if not self.auth_url:
            raise Exception("AUTH_URL not set. Call get_server_info() first.")

        # Parse JWT claims
        jwt_parts = self.session_id.split('.')
        if len(jwt_parts) != 3:
            raise Exception("Invalid JWT format")

        payload = jwt_parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding

        claims = json.loads(base64.urlsafe_b64decode(payload))
        sign = claims.get("s")

        if not sign:
            raise Exception("No 's' field in JWT claims")

        # Request tokens
        endpoint = "/vtdutoken2"
        params = {
            "ssid": self.session_id,
            "sign": sign,
        }

        response = requests.get(
            f"{self.auth_url}{endpoint}?{urlencode(params)}",
            headers=self._get_headers(include_session=True)
        )

        if response.status_code == 200:
            return response.json()

        return None


# ============================================================================
# STREAM CAPTURE
# ============================================================================

class EzvizStream:
    """EZVIZ video stream capture"""

    def __init__(self, api_client):
        self.api = api_client

    def _connect_socket(self, ip, port, timeout=10):
        """Create and connect TCP socket"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        return sock

    def _build_stream_url(self, vtm_ip, vtm_port, device_serial, token):
        """Build ysproto stream URL"""
        timestamp = int(1000 * time.time())
        return (
            f"ysproto://{vtm_ip}:{vtm_port}/live?"
            f"dev={device_serial}&chn=1&stream=1&cln=9&isp=0&auth=1&"
            f"ssn={token}&biz=1&vip=0&timestamp={timestamp}"
        )

    def _send_stream_request(self, sock, stream_url):
        """Send StreamInfoReq and receive response"""
        # Create and send request
        req_data = ProtobufEncoder.create_stream_info_req(stream_url)
        packet = VTMPacket.encode(req_data, EzvizConfig.MSG_STREAMINFO_REQ)
        sock.send(packet)

        # Receive response header
        header = sock.recv(8)
        header_info = VTMPacket.decode_header(header)

        # Receive response body
        body = sock.recv(header_info["length"])

        return header_info, body

    def capture(self, device_serial, output_file="stream.mpg", duration=30):
        """
        Capture video stream to file

        Args:
            device_serial: Device serial number
            output_file: Output filename
            duration: Recording duration in seconds

        Returns:
            dict with capture statistics
        """
        # Get device list
        devices = self.api.get_devices()
        if not devices:
            raise Exception("Failed to get device list")

        # Find device
        resource = None
        for res in devices.get("resourceInfos", []):
            if res["deviceSerial"] == device_serial and res.get("resourceType", 0) > 0:
                resource = res
                break

        if not resource:
            raise Exception(f"Device {device_serial} not found")

        # Get VTM info
        resource_id = resource["resourceId"]
        vtm_info = devices["VTM"].get(resource_id)

        if not vtm_info:
            raise Exception("VTM info not found")

        vtm_ip = vtm_info["externalIp"]
        vtm_port = vtm_info["port"]

        # Get tokens
        tokens = self.api.get_vtdu_tokens()
        if not tokens or not tokens.get("tokens"):
            raise Exception("Failed to get VTDU tokens")

        token = tokens["tokens"][0]

        # Connect to VTM
        stream_url = self._build_stream_url(vtm_ip, vtm_port, device_serial, token)
        vtm_sock = self._connect_socket(vtm_ip, vtm_port)

        try:
            # Get VTDU URL
            _, body = self._send_stream_request(vtm_sock, stream_url)
            body_str = body.decode('utf-8', errors='ignore')
            vtdu_url_start = body_str.find('ysproto://')
            vtdu_url = body_str[vtdu_url_start:].split('\x00')[0]

            # Parse VTDU address
            match = re.search(r'ysproto://([^:]+):(\d+)/', vtdu_url)
            vtdu_ip = match.group(1)
            vtdu_port = int(match.group(2))

        finally:
            vtm_sock.close()

        # Connect to VTDU
        vtdu_sock = self._connect_socket(vtdu_ip, vtdu_port, timeout=30)

        try:
            # Start streaming
            self._send_stream_request(vtdu_sock, vtdu_url)

            # Capture stream
            stats = self._capture_stream(vtdu_sock, output_file, duration)
            stats["vtdu_ip"] = vtdu_ip
            stats["vtdu_port"] = vtdu_port

            return stats

        finally:
            vtdu_sock.close()

    def _capture_stream(self, sock, output_file, duration):
        """Capture stream data to file"""
        packet_count = 0
        total_bytes = 0
        start_time = time.time()

        with open(output_file, 'wb') as f:
            while (time.time() - start_time) < duration:
                try:
                    # Read header
                    header = sock.recv(8)
                    if len(header) < 8:
                        continue

                    try:
                        header_info = VTMPacket.decode_header(header)

                        # Read body
                        body = sock.recv(header_info["length"])

                        # Save stream packets only
                        if header_info["channel"] == EzvizConfig.CHANNEL_UNENC_STREAM:
                            f.write(body)
                            packet_count += 1
                            total_bytes += len(body)

                            if packet_count % 100 == 0:
                                f.flush()

                    except ValueError:
                        # Not a valid header, continuation data
                        continue

                except socket.timeout:
                    break
                except Exception:
                    break

        elapsed = time.time() - start_time

        return {
            "packets": packet_count,
            "bytes": total_bytes,
            "duration": elapsed,
            "output_file": output_file
        }


# ============================================================================
# HIGH-LEVEL API
# ============================================================================

class EzvizCamera:
    """High-level EZVIZ camera interface"""

    def __init__(self, email, password, device_serial, region="Europe"):
        """
        Initialize EZVIZ camera

        Args:
            email: EZVIZ account email
            password: EZVIZ account password
            device_serial: Camera serial number
            region: Geographic region (Europe, Asia, NorthAmerica, SouthAmerica)
        """
        self.device_serial = device_serial
        self.api = EzvizAPI(email, password, region)
        self.stream = None
        self._connected = False

    def connect(self):
        """Connect to EZVIZ and authenticate"""
        if not self.api.login():
            raise Exception("Login failed")

        if not self.api.get_server_info():
            raise Exception("Failed to get server info")

        self.stream = EzvizStream(self.api)
        self._connected = True

        return True

    def capture_video(self, output_file="stream.mpg", duration=30):
        """
        Capture video stream

        Args:
            output_file: Output filename
            duration: Recording duration in seconds

        Returns:
            dict with capture statistics
        """
        if not self._connected:
            raise Exception("Not connected. Call connect() first.")

        return self.stream.capture(self.device_serial, output_file, duration)

    def get_devices(self):
        """Get list of all registered devices"""
        if not self._connected:
            raise Exception("Not connected. Call connect() first.")

        devices_data = self.api.get_devices()
        if not devices_data:
            return []

        devices = []
        for device in devices_data.get("deviceInfos", []):
            devices.append({
                "name": device.get("name"),
                "serial": device.get("deviceSerial"),
                "model": device.get("deviceType"),
                "status": device.get("status"),
                "version": device.get("version"),
            })

        return devices

    # ========================================================================
    # RTSP SERVER SUPPORT METHODS
    # ========================================================================

    def _get_stream_info(self):
        """
        Get VTDU connection info for streaming
        Used by RTSP server

        Returns:
            tuple: (vtdu_ip, vtdu_port, vtdu_url)
        """
        if not self._connected:
            raise Exception("Not connected. Call connect() first.")

        # Get device list
        devices = self.api.get_devices()
        if not devices:
            raise Exception("Failed to get device list")

        # Find device
        resource = None
        for res in devices.get("resourceInfos", []):
            if res["deviceSerial"] == self.device_serial and res.get("resourceType", 0) > 0:
                resource = res
                break

        if not resource:
            raise Exception(f"Device {self.device_serial} not found")

        # Get VTM info
        resource_id = resource["resourceId"]
        vtm_info = devices["VTM"].get(resource_id)

        if not vtm_info:
            raise Exception("VTM info not found")

        vtm_ip = vtm_info["externalIp"]
        vtm_port = vtm_info["port"]

        # Get tokens
        tokens_data = self.api.get_vtdu_tokens()
        if not tokens_data or not tokens_data.get("tokens"):
            raise Exception("Failed to get VTDU tokens")

        tokens = tokens_data["tokens"]

        # Connect to VTM to get VTDU redirect
        stream_url = self.stream._build_stream_url(vtm_ip, vtm_port, self.device_serial, tokens[0])
        vtm_sock = self.stream._connect_socket(vtm_ip, vtm_port)

        try:
            # Get VTDU URL
            _, body = self.stream._send_stream_request(vtm_sock, stream_url)
            body_str = body.decode('utf-8', errors='ignore')
            vtdu_url_start = body_str.find('ysproto://')
            vtdu_url = body_str[vtdu_url_start:].split('\x00')[0]

            # Parse VTDU address
            match = re.search(r'ysproto://([^:]+):(\d+)/', vtdu_url)
            vtdu_ip = match.group(1)
            vtdu_port = int(match.group(2))

            # Store for later use
            self._vtdu_url = vtdu_url

            return vtdu_ip, vtdu_port, vtdu_url

        finally:
            vtm_sock.close()

    def _build_stream_url(self, vtdu_ip, vtdu_port, token):
        """Build stream URL for RTSP server"""
        return self.stream._build_stream_url(vtdu_ip, vtdu_port, self.device_serial, token)

    def _create_stream_request(self, stream_url):
        """Create stream request packet for RTSP server"""
        req_data = ProtobufEncoder.create_stream_info_req(stream_url)
        packet = VTMPacket.encode(req_data, EzvizConfig.MSG_STREAMINFO_REQ)
        return packet

    def _parse_header(self, header):
        """Parse VTM packet header for RTSP server"""
        if len(header) < 8:
            raise ValueError("Header too short")

        magic, channel, length, seq, msg_code = struct.unpack('>BBHHH', header)

        if magic != EzvizConfig.MAGIC_BYTE:
            raise ValueError(f"Invalid magic byte: 0x{magic:02x}")

        return magic, channel, length, seq, msg_code


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Example usage"""
    import sys

    # Configuration
    EMAIL = "your@email.com"
    PASSWORD = "yourpassword"
    DEVICE_SERIAL = "YOUR_SERIAL"
    REGION = "Europe"

    if EMAIL == "your@email.com":
        print("Please edit the script and set your credentials!")
        print("EMAIL, PASSWORD, DEVICE_SERIAL")
        sys.exit(1)

    try:
        print("EZVIZ Stream Capture")
        print("=" * 60)

        # Create camera instance
        camera = EzvizCamera(EMAIL, PASSWORD, DEVICE_SERIAL, REGION)

        # Connect
        print("[1/2] Connecting...")
        camera.connect()
        print("✓ Connected")

        # Capture
        print("[2/2] Capturing stream...")
        stats = camera.capture_video("ezviz_stream.mpg", duration=30)

        print("\n" + "=" * 60)
        print("✓ Capture complete!")
        print(f"  File: {stats['output_file']}")
        print(f"  Packets: {stats['packets']}")
        print(f"  Size: {stats['bytes'] / 1024 / 1024:.2f} MB")
        print(f"  Duration: {stats['duration']:.1f}s")
        print("=" * 60)

        print("\nTo play:")
        print(f"  ffplay {stats['output_file']}")
        print(f"  vlc {stats['output_file']}")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
