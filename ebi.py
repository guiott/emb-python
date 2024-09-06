#!/usr/bin/python3

import sys
import serial, time

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
    def __init__(self,dev, debug=True):
        self.debug = debug
        if self.debug:
            print("---Start Init")
        self.dev = dev
        self.ser = serial.Serial(self.dev,baudrate=9600,timeout=.1)
        self.state = self.device_info()
        self.state.update(self.device_state())
        self.state.update(self.firmware_version())
        if self.debug:
            print("Init End---")
    def __del__(self):
        if getattr(self, 'ser', None):
            self.ser.close()
    def bcc(self, packet):
        return sum(packet) & 0xFF
    def hex(self, arr):
        return ':'.join(map(lambda x: '%02x' % x, arr))
    def read(self):
        ans = list(self.ser.read(2))
        if len(ans) != 2:
            return None
        length = (ans[0] << 8) + ans[1]
        ans += list(self.ser.read(length-2))
        if self.debug:
            print('   ans <-', self.hex(ans))
        assert(ans[-1] == self.bcc(ans[:-1]))
        return ans[2:-1]
    def send(self,command):
        n = len(command) + 3
        packet  = [n >> 8 & 0xFF, n & 0xFF]
        packet += command
        packet += [self.bcc(packet)]
        if self.debug:
            print('   cmd ->', self.hex(packet))
        self.ser.write(bytes(packet))
        ans = self.read()
        if ans != None:
            #print('Payload: ', self.hex(ans))
            assert(ans[0] == (command[0] | 0x80))
            return ans[1:]
        else:
            print("---NO ANSWER---")
            return
    def device_info(self):
        if self.debug:
            print('Device Info')
        ans = self.send([0x01])
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
        if self.debug:
            print('      Status  : ', EBI.DEVICE_STATE.get(ans[0], None))
        return { 'state': EBI.DEVICE_STATE.get(ans[0], None) }
    def reset(self):
        if self.debug:
            print("---Start Reset")        
        ans = self.send([0x05])
        _timeout = self.ser.timeout
        self.ser.timeout = 3
        boot = self.read()
        self.ser.timeout = _timeout
        assert(boot[0] == 0x84)
        self.state['state'] = boot[1]
        if self.debug:
            print('      Status  : ', EBI.STATUS.get(ans[0],ans[0]))
            print('      BOOT    : ', EBI.DEVICE_STATE.get(boot[1], None))
            print("END Reset---")
        return { 'status': EBI.STATUS.get(ans[0],ans[0]), 'boot_state': EBI.DEVICE_STATE.get(boot[1], None) }
    def firmware_version(self):
        if self.debug:
            print('Firmware Version')
        ans = self.send([0x06])
        if self.debug:
            print('      Firmware: ', self.hex(ans))
        return { 'firmware_version': self.hex(ans) }
    def output_power(self, power=None):
        if self.debug:
            print('Output Power')
        req_power = []
        try:
            req_power = [int(power) % 256]
        except:
            pass
        ans = self.send([0x10]+req_power)
        if req_power:
            return { 'status': EBI.STATUS.get(ans[0],ans[0]) }
        if self.debug:
            print('      Output Power: ', self.hex(ans))
        return { 'power': ans[0] }
    def operating_channel(self, channel=None, spreading_factor=None, bandwidth=None, coding_rate=None):
        if self.debug:
            print("Operating channel")
        req_channel = []
        if channel in EBI.LORA_CHANNEL and spreading_factor in EBI.LORA_SPREADING_FACTOR and \
            bandwidth in EBI.LORA_BANDWIDTH and coding_rate in EBI.LORA_CODING_RATE:
            req_channel = [channel, spreading_factor, bandwidth, coding_rate]
            print(req_channel)
        ans = self.send([0x11] + req_channel)
        if self.debug:
            print('      channel:', ans[0] )
        if req_channel:
            return { 'status': EBI.STATUS.get(ans[0],ans[0]) }
        return { 'channel': ans[0] }
    def energy_save(self, policy=None):
        if self.debug:
            print("Energy save")
        req_policy = []
        if policy in EBI.MODULE_SLEEP_POLICY:
            req_policy = [policy]
        ans = self.send([0x13] + req_policy)
        if req_policy:
            return { 'status': EBI.STATUS.get(ans[0],ans[0]) }
        return { 'policy': EBI.MODULE_SLEEP_POLICY.get(ans[0], ans[0]) }
    def region(self, region=None):
        if self.debug:
            print("Region")
        req_region = []
        if region:
            req_region = [region]
        ans = self.send([0x19] + req_region)
        if region:
            return { 'status': EBI.STATUS.get(ans[0],ans[0]) }
    def network_address(self, address=None):
        if self.debug:
            print('Network Address = DevAddr')
        req_address = []
        if address and len(address) in [2,4]:
            req_address = address
        ans = self.send([0x21] + req_address)
        if req_address:
            return { 'status': EBI.STATUS.get(ans[0],ans[0]) }
        return { 'address': self.hex(ans) }
    def network_identifier(self, identifier=None):
        if self.debug:
            print('Network Identifier')
        req_identifier = []
        if identifier and len(identifier) in [2,4]:
            req_identifier = identifier
        ans = self.send([0x22] + req_identifier)
        if req_identifier:
            return { 'status': EBI.STATUS.get(ans[0],ans[0]) }
        return { 'identifier': self.hex(ans) }
    def network_preference(self, protocol=None, auto_join=None, adr=None):
        if self.debug:
            print('Network Preferences')
        req_preference = []
        if protocol in [0,1] and auto_join in [0,1] and adr in [0,1]:
            req_preference = [(protocol << 7) + (auto_join << 6) + (adr << 5)]
        ans = self.send([0x25] + req_preference)
        if req_preference:
            return { 'status': EBI.STATUS.get(ans[0],ans[0]) }
        protocol = (ans[0] & 0x80) and "LoRaWAN" or "LoRaEMB"
        auto_join = (ans[0] & 0x40) != 0
        adr = (ans[0] & 0x20) != 0
        return { 'protocol': protocol, 'auto_join': auto_join, 'adr': adr }
    def network_stop(self):
        if self.debug:
            print("---Stop Network")
        _timeout = self.ser.timeout
        self.ser.timeout = 10
        ans = self.send([0x30])
        self.ser.timeout = _timeout
        return { 'status': EBI.STATUS.get(ans[0],ans[0]) }
    
    def network_start(self):
        if self.debug:
            print("---Start Network")
        _timeout = self.ser.timeout
        self.ser.timeout = 10
        ans = self.send([0x31])
        self.ser.timeout = _timeout
        return { 'status': EBI.STATUS.get(ans[0],ans[0]) }
    
    def send_data(self, payload, protocol=0, dst=None, port=1):
        assert(protocol in [0,1])
        if dst == None:
            dst = [0xff, 0xff]
        if protocol == 0: # LoRaEMB
            assert(len(dst)==2)
            options = [0x00, 0x00]
            header = options + dst
        else: # LoRaWAN
            assert(port in range(1,224))
            options = [0x40, 0x00]
            header = options + [port]
        ans = self.send([0x50] + header + payload)
        result = {
            'status':          EBI.STATUS.get(ans[0],ans[0]),
            'retries':         ans[1],
            'RSSI':            (ans[2] << 8) + ans[3],
        }
        if result['status'] == 'Success' and protocol == 1:
            result['tx_channel_mask'] = ans[4:5]
            result['tx_datarate_mask'] = ans[6]
            result['tx_power'] = ans[7]
            result['waiting_time'] = ans[8:12]
        return result
    def send_dataLW(self, payload, protocol=1, dst=None, port=6):
        assert(protocol in [0,1])
        if dst == None: 
            dst = [0xff, 0xff]
        if protocol == 0: # LoRaEMB
            assert(len(dst)==2)
            options = [0x00, 0x00]
            header = options + dst
        else: # LoRaWAN
            assert(port in range(1,224))
            options = [0x0D, 0x00]
            header = options + [port]

        _timeout = self.ser.timeout
        self.ser.timeout = 10
        ans = self.send([0x50] + header + payload)
        self.ser.timeout = _timeout

        result = {
            'status':          EBI.STATUS.get(ans[0],ans[0]),
            'retries':         ans[1],
            'RSSI':            (ans[2] << 8) + ans[3],
        }
        if result['status'] == 'Success':
            if len(ans) >= 6:
                result['tx_channel_mask'] = (ans[4] << 8) + ans[5]
            if len(ans) >= 7:
                result['tx_channel_mask'] = ans[4:5]
                result['tx_datarate_mask'] = ans[6]
                result['tx_power'] = ans[7]
                result['waiting_time'] = ans[8:12]
        return result
    def ieee_address(self, mac=None):
        if self.debug:
            print('IEEE ADDRESS')
        req_mac = []
        if mac:
            assert(len(mac) == 8)
            req_mac = mac
        ans = self.send([0x7e, 0x20] + req_mac)
        if req_mac:
            return { 'status': EBI.STATUS.get(ans[0],ans[0]) }
        return { 'ieee_address': self.hex(ans) }
    def physical_address(self, physical=None):
        if self.debug:
            print('Physical Address')
        req_physical = []
        if physical:
            assert(len(physical) == 16)
            req_physical = physical
        ans = self.send([0x20] + req_physical)
        if req_physical:
            return { 'status': EBI.STATUS.get(ans[0],ans[0]) }
        ans1=ans[:8]
        ans2=ans[8:]
        if self.debug:
            print("AppEUI",self.hex(ans1))
            print("DevEUI",self.hex(ans2))
        return { 'physical_address = AppEui + DevEui': self.hex(ans) }
    def receive(self, timeout=None):
        _timeout = self.ser.timeout
        self.ser.timeout = timeout
        ans = self.read()
        self.ser.timeout = _timeout
        if not ans:
            return
        assert(ans[0] == 0xe0)
        def signed(num, bits):
            if num & (1 <<(bits -1)):
                return num - (1 << bits)
            return num
        return {
            'options': self.hex(ans[1:3]),
            'rssi': signed((ans[4] << 8) + ans[3], 16),
            'src': self.hex(ans[5:7]),
            'dst': self.hex(ans[7:9]),
            'data': bytes(ans[9:]),
        }
    def device_default(self):
        self.debug == True
        print("RESET:", self.reset())
        print("DEVICE STATE", self.state)
        if self.state['state'] == 'Online':
            print("NETWORK STOP:", self.network_stop())
        print("OUTPUT POWER:", self.output_power())
        print("OUTPUT POWER -> +13dBm:", self.output_power(13))
        print("OUTPUT POWER:", self.output_power())
        print("OPERATING CHANNEL:", self.operating_channel())
        print("OPERATING CHANNEL -> CH 1 (868.100 MHz), SF 7, BW 125 kHz, CR 4/5:", self.operating_channel(1,7,0,1))
        print("OPERATING CHANNEL:", self.operating_channel())
        print("ENERGY SAVE:", self.energy_save())
        print("ENERGY SAVE -> ALWAYS ON: ", self.energy_save(0))
        print("ENERGY SAVE:", self.energy_save())
        print("NETWORK ADDRESS:", self.network_address())
        print("NETWORK ADDRESS -> 00:01:", self.network_address([0,1]))
        print("NETWORK ADDRESS:", self.network_address())
        print("NETWORK IDENTIFIER:", self.network_identifier())
        print("NETWORK IDENTIFIER -> 00:01:", self.network_identifier([0,1]))
        print("NETWORK IDENTIFIER:", self.network_identifier())
        print("NETWORK PREFERENCE:", self.network_preference())
        print("NETWORK START:", self.network_start())
        print("SEND DATA 01:02:03:04:", self.send_data(payload=[1,2,3,4]))
        print("NETWORK STOP:", self.network_stop())
        print("IEEE ADDRESS:", self.ieee_address())
        return(True)
    
    def device_report(self):
        print("---------------------------------------------")
        print("DEVICE STATE", self.state)
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
        print("AppKey:", self.app_key([0x2B,0x7E,0x15,0x16,0x28,0xAE,0xD2,0xA6,0xAB,0xF7,0x15,0x88,0x09,0xCF,0x4F,0x67]))
        print("---------------------------------------------")
        return(True)
    def app_key(self, key=None):
        if self.debug:
            print('AppKey')
        req_key = []
        if key and len(key) in [16]:
            req_key = key
        ans = self.send([0x26, 0x01] + req_key)
        if self.debug:
            print('AppKey:', self.hex(req_key))
        return { 'status': EBI.STATUS.get(ans[0],ans[0]) }
    
    def app_Skey(self, key=None):
        if self.debug:
            print('AppSKey')
        req_key = []
        if key and len(key) in [16]:
            req_key = key
        ans = self.send([0x26, 0x11] + req_key)
        print('AppSKey:', self.hex(req_key))
        return { 'status': EBI.STATUS.get(ans[0],ans[0]) }
    
    def nwk_Skey(self, key=None):
        if self.debug:
            print('NwkSKey')
        req_key = []
        if key and len(key) in [16]:
            req_key = key
        ans = self.send([0x26, 0x10] + req_key)
        print('NwkSKey:', self.hex(req_key))
        return { 'status': EBI.STATUS.get(ans[0],ans[0]) }
    

if __name__ == "__main__":
    device = "/dev/ttyS6"
    try:
        device = sys.argv[1]
    except:
        pass
    e = EBI(device, debug=False)
    e.device_default()
