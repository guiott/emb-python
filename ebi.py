#!/usr/bin/python3

import sys
import serial
import time
import logging

logger = logging.getLogger("ebi")
logger.setLevel(logging.ERROR)
file_handler = logging.FileHandler("/srv/samba/Acqua_Samba/emb-python/ebi_errors.log")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

class EBI:
    STATUS = {
        0x00: 'Success',
        0x01: 'Generic error',
        0x02: 'Parameters not accepted',
        0x03: 'Operation timeout',
        0x04: 'No memory',
        0x05: 'Unsupported',
        0x06: 'Busy',
        0x07: 'Cannot send',
    }
    PROTOCOL = {
        0x00: 'Unknown',
        0x01: 'Proprietary',
        0x10: '802.15.4',
        0x20: 'Zigbee',
        0x21: 'Zigbee 2004 (1.0)',
        0x22: 'Zigbee 2006',
        0x23: 'Zigbee 2007',
        0x24: 'Zigbee 2007-Pro',
        0x40: 'Wireless M-Bus',
        0x50: 'LoRa',
    }
    EMBIT_MODULE = {
        0x00: 'Unknown',
        0x10: 'Reserved',
        0x20: 'EMB-ZRF2xx',
        0x24: 'EMB-ZRF231xx',
        0x26: 'EMB-ZRF231PA',
        0x28: 'EMB-ZRF212xx',
        0x29: 'EMB-ZRF212B',
        0x30: 'EMB-Z253x',
        0x34: 'EMB-Z2530x',
        0x36: 'EMB-Z2530PA',
        0x38: 'EMB-Z2531x',
        0x3A: 'EMB-Z2531PA-USB',
        0x3C: 'EMB-Z2538x',
        0x3D: 'EMB-Z2538PA',
        0x40: 'EMB-WMBx',
        0x44: 'EMB-WMB169x',
        0x45: 'EMB-WMB169T',
        0x46: 'EMB-WMB169PA',
        0x48: 'EMB-WMB868x',
        0x49: 'EMB-WMB868',
        0x50: 'EMB-LRx',
        0x54: 'EMB-LR1272',
        0x55: 'EMB-LR1276S',
        0x60: 'EMB-AERx',
    }
    DEVICE_STATE = {
        0x00: 'Booting',
        0x01: 'Inside bootloader',
        0x10: 'Ready (startup operations completed successfully)',
        0x11: 'Ready (startup operations failed)',
        0x20: 'Offline',
        0x21: 'Connecting',
        0x22: 'Transparent mode startup',
        0x30: 'Online',
        0x40: 'Disconnecting',
        0x50: 'Reserved',
        0x51: 'End of receiving window',
        0x71: 'Firmware update over the air started',
        0x72: 'Firmware update over the air completed (reset required to switch to new fw)',
    }
    LORA_CHANNEL = {
        0x01: '868.100 MHz',
        0x02: '868.300 MHz',
        0x03: '868.500 MHz',
        0x04: '869.525 MHz',
    }
    LORA_SPREADING_FACTOR = {
        0x07: '128 Chips/symbol',
        0x08: '256 Chips/symbol',
        0x09: '512 Chips/symbol',
        0x0A: '1024 Chips/symbol',
        0x0B: '2048 Chips/symbol',
        0x0C: '4096 Chips/symbol',
    }
    LORA_BANDWIDTH = {
        0x00: '125 kHz',
        0x01: '250 kHz',
    }
    LORA_CODING_RATE = {
        0x01: '4/5',
        0x02: '4/6',
        0x03: '4/7',
        0x04: '4/8',
    }
    MODULE_SLEEP_POLICY = {
        0x00: 'ALWAYS ON',
        0x01: 'RX WINDOW',
        0x02: 'TX ONLY',
    }

    def __init__(self, dev, debug=False):
        self.debug = debug
        if self.debug:
            print("---Start Init")
        self.dev = dev
        # timeout prudente: molte operazioni fanno round-trip
        self.ser = serial.Serial(self.dev, baudrate=9600, timeout=0.1)
        # Init state (con protezioni)
        info = self.device_info()
        state = self.device_state()
        fw = self.firmware_version()
        self.state = {}
        if isinstance(info, dict):
            self.state.update(info)
        if isinstance(state, dict):
            self.state.update(state)
        if isinstance(fw, dict):
            self.state.update(fw)
        if self.debug:
            print("Init End---")

    def __del__(self):
        try:
            if getattr(self, 'ser', None):
                self.ser.close()
        except Exception:
            pass

    # -------------------- Helpers --------------------
    def bcc(self, packet):
        return sum(packet) & 0xFF

    def hex(self, arr):
        return ':'.join(map(lambda x: '%02x' % x, arr))

    def signed(self, num, bits):
        if num & (1 << (bits - 1)):
            return num - (1 << bits)
        return num

    def read(self):
        try:
            header = self.ser.read(2)
            if len(header) != 2:
                return None
            length = (header[0] << 8) + header[1]
            payload = list(self.ser.read(length - 2))
            ans = [header[0], header[1]] + payload
            if self.debug:
                print('   ans <-', self.hex(ans))
            if not ans:
                return None
            if ans[-1] != self.bcc(ans[:-1]):
                logger.error("read(): BCC mismatch")
                return None
            return ans[2:-1]
        except Exception as e:
            logger.error(f"read() exception: {e}")
            return None

    def send(self, command):
        try:
            n = len(command) + 3
            packet = [n >> 8 & 0xFF, n & 0xFF] + command
            packet += [self.bcc(packet)]
            if self.debug:
                print('   cmd ->', self.hex(packet))
            self.ser.write(bytes(packet))
            ans = self.read()
            if ans is None:
                logger.error("send(): no answer from module")
                return None
            # Verifica opcode echo (cmd | 0x80)
            expected = (command[0] | 0x80) & 0xFF
            if ans[0] != expected:
                logger.error(f"send(): unexpected opcode in answer: got 0x{ans[0]:02X}, expected 0x{expected:02X}")
                return None
            return ans[1:]
        except Exception as e:
            logger.error(f"send() exception: {e}")
            return None

    # -------------------- Info & Stato --------------------
    def device_info(self):
        if self.debug:
            print('Device Info')
        ans = self.send([0x01])
        if not ans or len(ans) < 2:
            logger.error("device_info(): no/short response")
            return {'status': 'NoResponse'}
        if self.debug:
            print('      Protocol: ', EBI.PROTOCOL.get(ans[0], None))
            print('      Module  : ', EBI.EMBIT_MODULE.get(ans[1], None))
            print('      MAC/UUID: ', self.hex(ans[2:]))
        return {
            'ebi_protocol': EBI.PROTOCOL.get(ans[0], None),
            'embit_module': EBI.EMBIT_MODULE.get(ans[1], None),
            'uuid': self.hex(ans[2:]),
        }

    def device_state(self):
        if self.debug:
            print('Device State')
        ans = self.send([0x04])
        if not ans:
            logger.error("device_state(): no response")
            return {'status': 'NoResponse'}
        if self.debug:
            print('      Status  : ', EBI.DEVICE_STATE.get(ans[0], None))
        return {'state': EBI.DEVICE_STATE.get(ans[0], None)}

    def reset(self):
        if self.debug:
            print("---Start Reset")
        ans = self.send([0x05])
        if not ans:
            logger.error("reset(): no response to reset command")
            return {'status': 'NoResponse'}
        _timeout = self.ser.timeout
        self.ser.timeout = 3
        boot = self.read()
        self.ser.timeout = _timeout
        if not boot or len(boot) < 2 or boot[0] != 0x84:
            logger.error("reset(): invalid/absent boot banner")
            return {'status': EBI.STATUS.get(ans[0], ans[0]), 'boot_state': None}
        self.state['state'] = EBI.DEVICE_STATE.get(boot[1], None)
        if self.debug:
            print('      Status  : ', EBI.STATUS.get(ans[0], ans[0]))
            print('      BOOT    : ', EBI.DEVICE_STATE.get(boot[1], None))
            print("END Reset---")
        return {'status': EBI.STATUS.get(ans[0], ans[0]), 'boot_state': EBI.DEVICE_STATE.get(boot[1], None)}

    def firmware_version(self):
        if self.debug:
            print('Firmware Version')
        ans = self.send([0x06])
        if not ans:
            logger.error("firmware_version(): no response")
            return {'status': 'NoResponse'}
        if self.debug:
            print('      Firmware: ', self.hex(ans))
        return {'firmware_version': self.hex(ans)}

    # -------------------- Config --------------------
    def uart(self, speed=None):
        if self.debug:
            print('UART config')
        req_speed = []
        try:
            if speed is not None:
                req_speed = [int(speed) % 256]
        except Exception:
            req_speed = []
        ans = self.send([0x09] + (req_speed or [0]))
        if not ans:
            logger.error("uart(): no response")
            return {'status': 'NoResponse'}
        if req_speed:
            return {'status': EBI.STATUS.get(ans[0], ans[0])}
        if self.debug:
            print('      Speed: ', self.hex(ans))
        return {'speed': ans[0]}

    def output_power(self, power=None):
        if self.debug:
            print('Output Power')
        req_power = []
        try:
            if power is not None:
                req_power = [int(power) % 256]
        except Exception:
            req_power = []
        ans = self.send([0x10] + req_power)
        if not ans:
            logger.error("output_power(): no response")
            return {'status': 'NoResponse'}
        if req_power:
            return {'status': EBI.STATUS.get(ans[0], ans[0])}
        if self.debug:
            print('      Output Power: ', self.hex(ans))
        return {'power': ans[0]}

    def operating_channel(self, channel=None, spreading_factor=None, bandwidth=None, coding_rate=None):
        if self.debug:
            print("Operating channel")
        req_channel = []
        if channel in EBI.LORA_CHANNEL and \
           spreading_factor in EBI.LORA_SPREADING_FACTOR and \
           bandwidth in EBI.LORA_BANDWIDTH and \
           coding_rate in EBI.LORA_CODING_RATE:
            req_channel = [channel, spreading_factor, bandwidth, coding_rate]
            if self.debug:
                print(req_channel)
        ans = self.send([0x11] + req_channel)
        if not ans:
            logger.error("operating_channel(): no response")
            return {'status': 'NoResponse'}
        if self.debug and ans:
            print('      channel:', ans[0])
        if req_channel:
            return {'status': EBI.STATUS.get(ans[0], ans[0])}
        return {'channel': ans[0]}

    def energy_save(self, policy=None):
        if self.debug:
            print("Energy save")
        req_policy = []
        if policy in EBI.MODULE_SLEEP_POLICY:
            req_policy = [policy]
        ans = self.send([0x13] + req_policy)
        if not ans:
            logger.error("energy_save(): no response")
            return {'status': 'NoResponse'}
        if req_policy:
            return {'status': EBI.STATUS.get(ans[0], ans[0])}
        return {'policy': EBI.MODULE_SLEEP_POLICY.get(ans[0], ans[0])}

    def region(self, region=None):
        if self.debug:
            print("Region")
        req_region = []
        if region is not None:
            req_region = [region]
        ans = self.send([0x19] + req_region)
        if not ans:
            logger.error("region(): no response")
            return {'status': 'NoResponse'}
        if req_region:
            return {'status': EBI.STATUS.get(ans[0], ans[0])}
        return {'status': EBI.STATUS.get(ans[0], ans[0])}

    def network_address(self, address=None):
        if self.debug:
            print('Network Address = DevAddr')
        req_address = []
        if address and len(address) in [2, 4]:
            req_address = address
        ans = self.send([0x21] + req_address)
        if not ans:
            logger.error("network_address(): no response")
            return {'status': 'NoResponse'}
        if req_address:
            return {'status': EBI.STATUS.get(ans[0], ans[0])}
        return {'address': self.hex(ans)}

    def network_identifier(self, identifier=None):
        if self.debug:
            print('Network Identifier')
        req_identifier = []
        if identifier and len(identifier) in [2, 4]:
            req_identifier = identifier
        ans = self.send([0x22] + req_identifier)
        if not ans:
            logger.error("network_identifier(): no response")
            return {'status': 'NoResponse'}
        if req_identifier:
            return {'status': EBI.STATUS.get(ans[0], ans[0])}
        return {'identifier': self.hex(ans)}

    def network_preference(self, protocol=None, auto_join=None, adr=None):
        if self.debug:
            print('Network Preferences')
        req_preference = []
        if protocol in [0, 1] and auto_join in [0, 1] and adr in [0, 1]:
            req_preference = [((protocol << 7) & 0x80) + ((auto_join << 6) & 0x40) + ((adr << 5) & 0x20)]
        ans = self.send([0x25] + req_preference)
        if not ans:
            logger.error("network_preference(): no response")
            return {'status': 'NoResponse'}
        if req_preference:
            return {'status': EBI.STATUS.get(ans[0], ans[0])}
        protocol = (ans[0] & 0x80) and "LoRaWAN" or "LoRaEMB"
        auto_join = (ans[0] & 0x40) != 0
        adr = (ans[0] & 0x20) != 0
        return {'protocol': protocol, 'auto_join': auto_join, 'adr': adr}

    def network_stop(self):
        if self.debug:
            print("---Stop Network")
        _timeout = self.ser.timeout
        self.ser.timeout = 10
        ans = self.send([0x30])
        self.ser.timeout = _timeout
        if not ans:
            logger.error("network_stop(): no response")
            return {'status': 'NoResponse'}
        return {'status': EBI.STATUS.get(ans[0], ans[0])}

    def network_start(self):
        if self.debug:
            print("---Start Network")
        _timeout = self.ser.timeout
        self.ser.timeout = 10
        ans = self.send([0x31])
        self.ser.timeout = _timeout
        if not ans:
            logger.error("network_start(): no response")
            return {'status': 'NoResponse'}
        return {'status': EBI.STATUS.get(ans[0], ans[0])}

    # -------------------- TX/RX --------------------
    def send_data(self, payload, protocol=0, dst=None, port=1):
        try:
            assert protocol in [0, 1]
            if dst is None:
                dst = [0xff, 0xff]
            if protocol == 0:  # LoRaEMB
                assert len(dst) == 2
                options = [0x00, 0x00]
                header = options + dst
            else:  # LoRaWAN
                assert port in range(1, 224)
                options = [0x40, 0x00]
                header = options + [port]
            ans = self.send([0x50] + header + payload)
            if not ans or len(ans) < 4:
                logger.error("send_data(): no/short response")
                return {'status': 'NoResponse'}
            result = {
                'status': EBI.STATUS.get(ans[0], ans[0]),
                'retries': ans[1],
                'RSSI': (ans[2] << 8) + ans[3],
            }
            if result['status'] == 'Success' and protocol == 1:
                if len(ans) >= 6:
                    result['tx_channel_mask'] = ans[4:6]
                if len(ans) >= 8:
                    result['tx_datarate_mask'] = ans[6]
                    result['tx_power'] = ans[7]
                if len(ans) >= 12:
                    result['waiting_time'] = ans[8:12]
            return result
        except Exception as e:
            logger.error(f"send_data() exception: {e}")
            return {'status': 'Exception', 'error': str(e)}

    def send_dataLW(self, payload, protocol=1, dst=None, port=6):
        try:
            assert protocol in [0, 1]
            if dst is None:
                dst = [0xff, 0xff]
            if protocol == 0:  # LoRaEMB
                assert len(dst) == 2
                options = [0x00, 0x00]
                header = options + dst
            else:  # LoRaWAN
                assert port in range(1, 224)
                options = [0x0D, 0x00]
                header = options + [port]
            _timeout = self.ser.timeout
            self.ser.timeout = 10
            ans = self.send([0x50] + header + payload)
            self.ser.timeout = _timeout
            if not ans or len(ans) < 4:
                logger.error("send_dataLW(): no/short response")
                return {'status': 'NoResponse'}
            result = {
                'status': EBI.STATUS.get(ans[0], ans[0]),
                'retries': ans[1],
                'RSSI': self.signed(((ans[2] << 8) + ans[3]), 16),
            }
            if result['status'] == 'Success':
                if len(ans) >= 6:
                    result['tx_channel_mask'] = (ans[4] << 8) + ans[5]
                if len(ans) >= 8:
                    result['tx_datarate_mask'] = ans[6]
                    result['tx_power'] = ans[7]
                if len(ans) >= 12:
                    result['waiting_time'] = ans[8:12]
            return result
        except Exception as e:
            logger.error(f"send_dataLW() exception: {e}")
            return {'status': 'Exception', 'error': str(e)}

    def ieee_address(self, mac=None):
        if self.debug:
            print('IEEE ADDRESS')
        req_mac = []
        if mac:
            try:
                assert len(mac) == 8
                req_mac = mac
            except Exception:
                req_mac = []
        ans = self.send([0x7E, 0x20] + req_mac)
        if not ans:
            logger.error("ieee_address(): no response")
            return {'status': 'NoResponse'}
        if req_mac:
            return {'status': EBI.STATUS.get(ans[0], ans[0])}
        return {'ieee_address': self.hex(ans)}

    def physical_address(self, physical=None):
        if self.debug:
            print('Physical Address')
        req_physical = []
        if physical:
            try:
                assert len(physical) == 16
                req_physical = physical
            except Exception:
                req_physical = []
        ans = self.send([0x20] + req_physical)
        if not ans:
            logger.error("physical_address(): no response")
            return {'status': 'NoResponse'}
        if req_physical:
            return {'status': EBI.STATUS.get(ans[0], ans[0])}
        ans1 = ans[:8]
        ans2 = ans[8:]
        if self.debug:
            print("AppEUI", self.hex(ans1))
            print("DevEUI", self.hex(ans2))
        return {'physical_address = AppEui + DevEui': self.hex(ans)}

    def receive(self, protocol=0, timeout=None):
        _timeout = self.ser.timeout
        self.ser.timeout = timeout
        ans = self.read()
        self.ser.timeout = _timeout
        if not ans:
            return None, None, None, None
        if ans[0] != 0xE0:
            logger.error(f"receive(): unexpected header 0x{ans[0]:02X}")
            return None, None, None, None
        if protocol == 1:
            # LoRaEMB (schema non usato nel resto del tuo codice, ma lo lascio)
            try:
                return {
                    'options': self.hex(ans[1:3]),
                    'rssi': self.signed((ans[4] << 8) + ans[3], 16),
                    'src': self.hex(ans[5:7]),
                    'dst': self.hex(ans[7:9]),
                    'data': chr(ans[9:]),
                }
            except Exception as e:
                logger.error(f"receive(EMB) parse error: {e}")
                return None, None, None, None
        else:
            # LoRaWAN
            try:
                options = self.hex(ans[1:3])
                RSSI = self.signed((ans[3] << 8) + ans[4], 16)
                FPort = ans[6]
                RXstr = ans[7:]
                data = ''.join(map(chr, RXstr))
                return options, RSSI, FPort, data
            except Exception as e:
                logger.error(f"receive(LW) parse error: {e}")
                return None, None, None, None

    # -------------------- Utility verbose/demo --------------------
    def device_default(self):
        try:
            self.debug = True
            print("RESET:", self.reset())
            print("DEVICE STATE", self.state)
            if self.state.get('state') == 'Online':
                print("NETWORK STOP:", self.network_stop())
            print("OUTPUT POWER:", self.output_power())
            print("OUTPUT POWER -> +13dBm:", self.output_power(13))
            print("OUTPUT POWER:", self.output_power())
            print("OPERATING CHANNEL:", self.operating_channel())
            print("OPERATING CHANNEL -> CH 1 (868.100 MHz), SF 7, BW 125 kHz, CR 4/5:",
                  self.operating_channel(1, 7, 0, 1))
            print("OPERATING CHANNEL:", self.operating_channel())
            print("ENERGY SAVE:", self.energy_save())
            print("ENERGY SAVE -> ALWAYS ON:", self.energy_save(0))
            print("ENERGY SAVE:", self.energy_save())
            print("NETWORK ADDRESS:", self.network_address())
            print("NETWORK ADDRESS -> 00:01:", self.network_address([0, 1]))
            print("NETWORK ADDRESS:", self.network_address())
            print("NETWORK IDENTIFIER:", self.network_identifier())
            print("NETWORK IDENTIFIER -> 00:01:", self.network_identifier([0, 1]))
            print("NETWORK IDENTIFIER:", self.network_identifier())
            print("NETWORK PREFERENCE:", self.network_preference())
            print("NETWORK START:", self.network_start())
            print("SEND DATA 01:02:03:04:", self.send_data(payload=[1, 2, 3, 4]))
            print("NETWORK STOP:", self.network_stop())
            print("IEEE ADDRESS:", self.ieee_address())
            return True
        except Exception as e:
            logger.error(f"device_default() exception: {e}")
            return {'status': 'Exception', 'error': str(e)}

    def device_report(self):
        try:
            print("---------------------------------------------")
            print("DEVICE STATE", self.state)
            print("---------------------------------------------")
            print("REGION", self.region())
            print("---------------------------------------------")
            print("OUTPUT POWER:", self.output_power())
            print("---------------------------------------------")
            print("OPERATING CHANNEL:", self.operating_channel())
            print("---------------------------------------------")
            print("ENERGY SAVE:", self.energy_save())
            print("---------------------------------------------")
            print("NETWORK ADDRESS:", self.network_address())
            print("---------------------------------------------")
            print("NETWORK IDENTIFIER:", self.network_identifier())
            print("---------------------------------------------")
            print("NETWORK PREFERENCE:", self.network_preference())
            print("---------------------------------------------")
            print("IEEE ADDRESS:", self.ieee_address())
            print("---------------------------------------------")
            print("PHYSICAL ADDRESS:", self.physical_address())
            print("---------------------------------------------")
            print("AppKey:", self.app_key([0x2B, 0x7E, 0x15, 0x16,
                                             0x28, 0xAE, 0xD2, 0xA6,
                                             0xAB, 0xF7, 0x15, 0x88,
                                             0x09, 0xCF, 0x4F, 0x67]))
            print("---------------------------------------------")
            return True
        except Exception as e:
            logger.error(f"device_report() exception: {e}")
            return {'status': 'Exception', 'error': str(e)}

    def app_key(self, key=None):
        try:
            req_key = key if (key and len(key) == 16) else []
            ans = self.send([0x26, 0x01] + req_key)
            if not ans:
                logger.error("app_key(): no response")
                return {'status': 'NoResponse'}
            return {'status': EBI.STATUS.get(ans[0], ans[0])}
        except Exception as e:
            logger.error(f"app_key() exception: {e}")
            return {'status': 'Exception', 'error': str(e)}

    def app_Skey(self, key=None):
        try:
            req_key = key if (key and len(key) == 16) else []
            ans = self.send([0x26, 0x11] + req_key)
            if not ans:
                logger.error("app_Skey(): no response")
                return {'status': 'NoResponse'}
            return {'status': EBI.STATUS.get(ans[0], ans[0])}
        except Exception as e:
            logger.error(f"app_Skey() exception: {e}")
            return {'status': 'Exception', 'error': str(e)}

    def nwk_Skey(self, key=None):
        try:
            req_key = key if (key and len(key) == 16) else []
            ans = self.send([0x26, 0x10] + req_key)
            if not ans:
                logger.error("nwk_Skey(): no response")
                return {'status': 'NoResponse'}
            return {'status': EBI.STATUS.get(ans[0], ans[0])}
        except Exception as e:
            logger.error(f"nwk_Skey() exception: {e}")
            return {'status': 'Exception', 'error': str(e)}


if __name__ == "__main__":
    # Piccolo test manuale: stampa un report e prova un paio di comandi.
    # Esempio: python3 ebi.py /dev/ttyS6
    dev = "/dev/ttyS6"
    try:
        dev = sys.argv[1]
    except Exception:
        pass

    # Configurazione logging di base solo se l'app chiamante non ha già handler
    if not logger.handlers:
        h = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        h.setFormatter(fmt)
        logger.addHandler(h)
        logger.setLevel(logging.INFO)

    e = EBI(dev, debug=False)
    e.device_report()
