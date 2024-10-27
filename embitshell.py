#!/usr/bin/python3

import cmd, sys, readline, shlex
from ebi import EBI

import time

#GPIO definitions=======
import gpiod
chipA=gpiod.Chip('gpiochip0')
chipB=gpiod.Chip('gpiochip1')
chipC=gpiod.Chip('gpiochip2')
chipD=gpiod.Chip('gpiochip3')
chipE=gpiod.Chip('gpiochip4')

def GPIO_conf(pin_name, chip_name, consumer_name, direction, default_val=0):
    line = gpiod.find_line(pin_name)
    if line is None:
        raise Exception(f"GPIO {pin_name} not found")
    GPIO_line = chip_name.get_lines([line.offset()])
    if direction == "out":
        GPIO_line.request(consumer=consumer_name, type=gpiod.LINE_REQ_DIR_OUT, default_vals=[default_val])
    elif direction == "in":
        GPIO_line.request(consumer=consumer_name, type=gpiod.LINE_REQ_DIR_IN)
    else:
        raise ValueError("set direction to 'in' or 'out'")
    return GPIO_line

Rel1 = GPIO_conf("pioA13", chipA, "Rel1", "out", 0)
Rel2 = GPIO_conf("pioA14", chipA, "Rel2", "out", 0)
led_green = GPIO_conf("pioD26", chipD, "led_green", "out", 1)
led_red = GPIO_conf("pioD14", chipD, "led_red", "out", 1)
rgb_red = GPIO_conf("pioD19", chipD, "RGB_red", "out", 1)
rgb_green = GPIO_conf("pioD31", chipD, "RGB_green", "out", 1)
rgb_blue = GPIO_conf("pioD30", chipD, "RGB_blue", "out", 1)
DIG_OUT1 = GPIO_conf("pioC13", chipC, "DIG_OUT1", "out", 0)
DIG_OUT2 = GPIO_conf("pioC12", chipC, "DIG_OUT2", "out", 0)
PCIe_ON = GPIO_conf("pioC20", chipC, "PCIe_ON", "out", 0)
DIG_IN1 = GPIO_conf("pioA15", chipA, "DIG_IN1", "in")
DIG_IN2 = GPIO_conf("pioC14", chipC, "DIG_IN2", "in")

def Rel(RelN, RelState='OFF'):
    if(RelState == 'ON'):
        State=1
    else:
        State=0

    if(RelN=='1'):
        Rel1.set_values([State])
    elif(RelN=='2'):
        Rel2.set_values([State])
    else:
        Rel1.set_values([0])
        Rel2.set_values([0])

leds = ['r','g','R','G','B']
def Led(LED, LedState='OFF'):
    if(LedState == 'ON'):
        State=0
    else:
        State=1

    if(LED=='g'):
        led_green.set_values([State])
    elif(LED=='r'):
        led_red.set_values([State])
    elif(LED=='R'):
        rgb_red.set_values([State])
    elif(LED=='G'):
        rgb_green.set_values([State])
    elif(LED=='B'):
        rgb_blue.set_values([State])
    else:
        led_green.set_values([1])
        led_green.set_values([1])
        rgb_red.set_values([1])
        rgb_green.set_values([1])
        rgb_blue.set_values([1])

digs = ['P', '1', '2']
def Dig(digN, digStatus):
    if(digStatus == 'ON'):
        State=1
    else:
        State=0    
    if(digN=='P'):
        PCIe_ON.set_values([State])
    elif(digN=='1'):
        DIG_OUT1.set_values([State])
    elif(digN=='2'):
        DIG_OUT2.set_values([State])
    else:
        PCIe_ON.set_values([0])
        DIG_OUT1.set_values([0])
        DIG_OUT2.set_values([0])

def AllOFF():
    Rel(1, 'OFF')
    Led('g', 'OFF')
    Rel(2, 'OFF') 
    Led('r', 'OFF')
    Led('rgb_r','OFF')
    Led('rgb_g','OFF')
    Led('rgb_b','OFF')
    PCIe_ON.set_values([0])
    DIG_OUT1.set_values([0])
    DIG_OUT2.set_values([0])

def deviceSet(self, devType, devNum, devStatus):  
    #print(devType, devNum, devStatus)
    if devType == 'R':
        if devNum in ['1', '2']:
            if devStatus in ['ON', 'OFF']:
                Rel(devNum, devStatus)
            else:
                if self._e.debug:
                    print("Dev Status not recognized")
        else:
            if self._e.debug:
                print("Dev Num not recognized") 
    elif devType == 'L':
        if devNum in leds:
            if devStatus in ['ON', 'OFF']:
                Led(devNum, devStatus)
            else:
                if self._e.debug:
                    print("Dev Status not recognized")
        else:
            if self._e.debug:
                print("Dev Num not recognized") 
    elif devType == 'D':
        if devNum in digs:
            if devStatus in ['ON', 'OFF']:
                Dig(devNum, devStatus)
            else:
                if self._e.debug:
                    print("Dev Status not recognized")
        else:
            if self._e.debug:
                print("Dev Num not recognized") 
    elif devType == 'A':
        AllOFF()
    else:
        if self._e.debug:
            print("Dev Type not recognized")  
#=======GPIO definitions

#rename config.py_TEMPLATE config.py and edit your keys accordingly
import config
phyAddr = config.phyAddr
netProtocol = config.netProtocol 
autoJoin = config.autoJoin
adr = config.adr
appKey = config.appKey
RXtimeout = config.RXtimeout

class EmbitShell(cmd.Cmd):

    prompt = "EMB> "

    def __init__(self, device):
        self._e = EBI(device)
        self._e.reset()
        state = self._e.state
        self.intro = "EMBIT module {embit_module} - FW {firmware_version}\n".format(**state)
        if state['state'] == 'Online':
            self._e.network_stop()
        self._e.energy_save(0x00) # Always on
        self._params = { 'channel': 1, 'sf': 7, 'bw': 0, 'cr': 1 } # 868.100 MHz, 128 Chips/symbol, 125 kHz, 4/5
        self._e.operating_channel(*self._params.values())
        self._e.network_start()
        super().__init__()

    def default(self, line):
        if line == "EOF":
            if self._e.debug:
                print("\nBye!")
            AllOFF()
            return True
        return super().default(line)

    def do_debug(self, arg):
        """toggle debug mode
Usage: debug"""
        self._e.debug = not self._e.debug
        if self._e.debug:
            print("{'debug': %s}" % self._e.debug)

    def do_state(self, arg):
        """get device state
Usage: state"""
        ret = self._e.device_state()
        if self._e.debug:
            print(ret)

    def do_reset(self, arg):
        """reset device
Usage: reset"""
        ret = self._e.reset()
        if self._e.debug:
            print(ret)

    def do_power(self, arg):
        """get or set device power
Usage: power [value]

value: [0-256]"""
        value = None
        if arg:
            try:
                value = int(arg) % 256
            except ValueError:
                if self._e.debug:
                    print("Invalid power value {}".format(arg))
                return
        state = self._e.device_state()
        should_stop = value and state['state'] == 'Online'
        if should_stop:
            self._e.network_stop()
        ret = self._e.output_power(value)
        if should_stop:
            self._e.network_start()
        if self._e.debug:
            print(ret)

    def do_channel(self, arg):
        """get or set device channel parameters
Usage: channel [ch sf bw cr]

ch: 0x01 -> 868.100 MHz
    0x02 -> 868.300 MHz
    0x03 -> 868.500 MHz
    0x04 -> 869.525 MHz
sf: 0x07 -> 128 Chips/symbol
    0x08 -> 256 Chips/symbol
    0x09 -> 512 Chips/symbol
    0x0A -> 1024 Chips/symbol
    0x0B -> 2048 Chips/symbol
    0x0C -> 4096 Chips/symbol
bw: 0x00 -> 125 kHz
    0x01 -> 250 kHz
cr: 0x01 -> 4/5
    0x02 -> 4/6
    0x03 -> 4/7
    0x04 -> 4/8"""
        channel, spreading_factor, bandwidth, coding_rate = [None]*4
        args = (arg.split() + [""]*4)[:4]
        if args[0]:
            try:
                channel = int(args[0])
                EBI.LORA_CHANNEL[channel]
            except (ValueError, KeyError):
                print("Invalid channel value {}".format(args[0]))
                return
            try:
                spreading_factor = int(args[1])
                EBI.LORA_SPREADING_FACTOR[spreading_factor]
            except (ValueError, KeyError):
                print("Invalid spreading factor value {}".format(args[1]))
                return
            try:
                bandwidth = int(args[2])
                EBI.LORA_BANDWIDTH[bandwidth]
            except (ValueError, KeyError):
                print("Invalid bandwith value {}".format(args[2]))
                return
            try:
                coding_rate = int(args[3])
                EBI.LORA_CODING_RATE[coding_rate]
            except (ValueError, KeyError):
                print("Invalid coding rate value {}".format(args[3]))
                return
        state = self._e.device_state()
        should_stop = channel and state['state'] == 'Online'
        if should_stop:
            self._e.network_stop()
        ret = self._e.operating_channel(channel, spreading_factor, bandwidth, coding_rate)
        if channel and ret.get('status','') == 'Success':
            self._params = { 'channel': channel, 'sf': spreading_factor, 'bw': bandwidth, 'cr': coding_rate }
        if 'channel' in ret:
            assert(ret['channel'] == self._params['channel'])
        ret.update(self._params)
        if should_stop:
            self._e.network_start()
        if self._e.debug:
            print(ret)

    def do_address(self, arg):
        """get or set device address
Usage: address [value]

value: [0-65535]"""
        value = None
        if arg:
            try:
                value = int(arg)
                value = [ (value & 0xFF00) >> 8, value & 0x00FF ]
            except ValueError:
                print("Invalid address value {}".format(arg))
                return
        state = self._e.device_state()
        should_stop = value and state['state'] == 'Online'
        if should_stop:
            self._e.network_stop()
        ret = self._e.network_address(value)
        if should_stop:
            self._e.network_start()
        if self._e.debug:
            print(ret)

    def do_region(self, arg):
        """get or set device address
Usage: region [value]

value: [0-1-2]"""
        value = None
        state = self._e.device_state()
        should_stop = value and state['state'] == 'Online'
        if should_stop:
            self._e.network_stop()
        ret = self._e.region(value)
        if should_stop:
            self._e.network_start()
        if self._e.debug:
            print(ret)

    def do_network(self, arg):
        """get or set device network identifier
Usage: network [value]

value: [0-65535]"""
        value = None
        if arg:
            try:
                value = int(arg)
                value = [ (value & 0xFF00) >> 8, value & 0x00FF ]
            except ValueError:
                print("Invalid network value {}".format(arg))
                return
        state = self._e.device_state()
        should_stop = value and state['state'] == 'Online'
        if should_stop:
            self._e.network_stop()
        ret = self._e.network_identifier(value)
        if should_stop:
            self._e.network_start()
        if self._e.debug:
            print(ret)

    def do_send_EMB(self, arg):
        """send a network packet using LoRaEMB protocol
Usage: send_EMB payload [dest]

dest: [0-65535]; specify no dest for broadcast"""
        if not arg:
            print("Please specify a payload to send")
            return
        payload, dst = (shlex.split(arg)+[None])[:2]
        payload = list(bytes(payload, 'utf8'))
        if dst != None:
            try:
                dst = int(dst)
                dst = [ (dst & 0xFF00) >> 8, dst & 0x00FF ]
            except ValueError:
                print("Invalid destination value {}".format(dst))
                return
        ret = self._e.send_data(payload=payload, dst=dst)
        if self._e.debug:
            print(ret)

    def do_send(self, arg):
        """send a network packet using LoRaWAN protocol
Usage: send payload [dest]

dest: [0-65535]; specify no dest for broadcast"""
        if not arg:
            print("Please specify a payload to send")
            return
        payload, dst = (shlex.split(arg)+[None])[:2]
        payload = list(bytes(payload, 'utf8'))
        if self._e.debug:
            print(payload)
            print(dst)  
        if dst != None:
            try:
                dst = int(dst)
                dst = [ (dst & 0xFF00) >> 8, dst & 0x00FF ]
            except ValueError:
                print("Invalid destination value {}".format(dst))
                return
        ret = self._e.send_dataLW(payload=payload, dst=dst)
        if self._e.debug:
            print(ret)

    def do_report(self, arg):
        """print all the setting parameter
Usage: report"""
        #self._e.debug = False
        print("{'debug': %s}" % self._e.debug)  
        print("==========================================")      
        ret = self._e.device_report()
        print("==========================================")  
        #self._e.debug = True
        print("{'debug': %s}" % self._e.debug)  
    
    def do_default(self, arg):
        """reset all the setting parameter to default
Usage: default"""
        #self._e.debug = False
        print("{'debug': %s}" % self._e.debug)  
        print("==========================================")      
        ret = self._e.device_default()
        print("==========================================")  
        #self._e.debug = True
        print("{'debug': %s}" % self._e.debug)  
    
    def do_receive(self, arg1=None):
        """receive a network packet and print it
Usage: receive protocol 0 = LoRaWAN - 1 = EMB

timeout in seconds; specify no timeout to wait forever"""
        if arg1:
            options, RSSI, FPort, data = self._e.receive(arg1, RXtimeout)
        else:
            options, RSSI, FPort, data = self._e.receive(0, RXtimeout)
        if self._e.debug:
            print("Opt: ", options, " - RSSI:" , RSSI, " - FPort: ", FPort, " - Data: ", data)
        if RSSI:
            dataSplit=data.split(":")
            deviceSet(self, dataSplit[0], dataSplit[1], dataSplit[2])

    def do_abp(self, arg):
        """set lorawan protocol parameters with ABP (NO auto join)
Usage: set LoRaWAN manually

value: [0-65535]"""
        value = arg   
        if self._e.debug:
            print("=============================================")
        state = self._e.device_state()
        if state['state'] == 'Online':
            should_stop = True
        else:
            should_stop = False
        if should_stop:
            self._e.network_stop()
        if self._e.debug:
            print("=============================================")
        ret = self._e.network_preference(1,0,1)
        if self._e.debug:
            print(ret)
            print("---------------------------------------------")
        ret = self._e.network_preference()
        if self._e.debug:
            print(ret)
            print("=============================================")
        # Physical Address = AppEui + DevEui
        ret = self._e.physical_address([0x70, 0xB3, 0xD5, 0x7E, 0xD0, 0x06, 0x9E, 0x89, 0x70, 0xB3, 0xD5, 0x7E, 0xD0, 0x06, 0x9E, 0x89])
        if self._e.debug:
            print(ret)
            print("------------------------------------------")
        ret = self._e.physical_address()
        if self._e.debug:   
            print(ret)
            print("=============================================")
        #Network Address = DevAddr
        ret = self._e.network_address([0x26, 0x0B, 0x6E, 0x5D])
        if self._e.debug:
            print(ret)
            print("---------------------------------------------")
        ret = self._e.network_address()
        if self._e.debug:
            print(ret)
            print("=============================================")
        ret = self._e.app_Skey([0xB6, 0x26, 0x73, 0x5F, 0x1C, 0x34, 0x27, 0x67, 0x65, 0x68, 0x5F, 0xB8, 0xA1, 0xD2, 0x1F, 0x47])
        if self._e.debug:
            print(ret)
            print("=============================================")
        ret = self._e.nwk_Skey([0xFD, 0xC8, 0xC6, 0x7C, 0x1D, 0x0F, 0xFB, 0x56, 0x24, 0x1B, 0x6C, 0x88, 0x2E, 0xE3, 0x3A, 0xA7])
        if self._e.debug:
            print(ret)        
            print("=============================================")
        #Energy save option 01 = Class A 
        ret = self._e.energy_save()
        if self._e.debug:
            print(ret)
            print("=============================================")
        #Power
        ret = self._e.output_power(0x0E)
        if self._e.debug:
            print(ret)
        ret = self._e.output_power()
        if self._e.debug:
            print(ret)
            print("=============================================")
        #Power
        ret = self._e.operating_channel(1,9,0,1)
        if self._e.debug:
            print(ret)
            print("=============================================")
        #Region
        ret = self._e.region(0)
        if self._e.debug:
            print(ret)
            print("=============================================")
            print(self._e.device_state())
        self._e.network_start()
        if self._e.debug:
            print(self._e.device_state())
            print("---------------------------------------------")

        #if should_stop:
            #self._e.network_start()

    def do_lorawan(self, arg):
        """set lorawan protocol parameters with auto join. Class = arg
Usage: lorawan 0, 1, 2

value: [0-1-2]"""
        value = 0
        if arg:
            value = int(arg)
            if value > 2:
                if self._e.debug:
                    print("Invalid Class {}".format(arg))
                return  
        state = self._e.device_state()
        if state['state'] == 'Online':
            should_stop = True
        else:
            should_stop = False
        if should_stop:
            self._e.network_stop()

        ret = self._e.physical_address(phyAddr)
        if self._e.debug:
            print(ret)
        ret = self._e.physical_address()
        if self._e.debug:
            print(ret)

        ret = self._e.network_preference(netProtocol,autoJoin,adr)
        if self._e.debug:
            print(ret)
        ret = self._e.network_preference()
        if self._e.debug:
            print(ret)

        ret = self._e.app_key(appKey)
        if self._e.debug:
            print(ret)

        #Energy save option 00 = Class C - 01 = Class A - 02 = TX Only
        ret = self._e.energy_save(value)
        if self._e.debug:
            print(ret)
        if self._e.debug:
            print(self._e.energy_save())  

        self._e.network_start()

    def do_app_key(self, arg):
        """set device AppKey
Usage: AppKey [value]

value: [16 byte]"""
        value = None
        if arg:
            try:
                value = int(arg)
                value = [ (value & 0xFF00) >> 16, value & 0x00FF ]
            except ValueError:
                print("Invalid address value {}".format(arg))
                return
        state = self._e.device_state()
        should_stop = value and state['state'] == 'Online'
        if should_stop:
            self._e.network_stop()
        #ret = self._e.app_key(value)
        ret = self._e.app_key(appKey)
        if self._e.debug:
            print(ret)

    def do_start(self, arg):
        """network start
Usage: start

value: [0-65535]"""
        self._e.network_start()
        if self._e.debug:
            print(self._e.device_state())

    def do_stop(self, arg):
        """network stop
Usage: stop

value: [0-65535]"""
        self._e.network_stop()
        if self._e.debug:
            print(self._e.device_state())

def do_quit(self, arg):
        """quit EMB shell
Usage: quit"""
        if self._e.debug:
            print("\nBye!")
        AllOFF()
        return True

if __name__ == '__main__':
    device = "/dev/ttyS6"
    try:
        device = sys.argv[1]
    except:
        pass
    shell = EmbitShell(device)
    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        print("\nBye!")
        AllOFF()


