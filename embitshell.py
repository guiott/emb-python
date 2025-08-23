#!/usr/bin/env python3

import cmd, sys, readline, shlex
from ebi import EBI

import time
from time import localtime, strftime

from colorama import Fore, Style

# ============ LOGGING ===============
import logging
logger = logging.getLogger("embitshell")
logger.setLevel(logging.ERROR)
file_handler = logging.FileHandler("/srv/samba/Acqua_Samba/emb-python/embitshell_errors.log")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
# ====================================

#=RS485 external program=======
import subprocess, atexit
from pathlib import Path 

# ================= RS485 runner (KMT_RS485.py) =================
# Percorso al programma KMT_RS485.py (adatta al tuo path reale)
RS485_PROG = str(Path(__file__).resolve().parent / "KMT_RS485.py")
RS485_PORT = "/dev/ttyS4"   # porta RS485
RS485_ID   = "1"            # ID scheda KMTronic

_rs485 = None  # processo persistente

def _rs485_start():
    """Avvia KMT_RS485.py in modalità interattiva (stdin aperta)."""
    global _rs485
    if _rs485 is None or _rs485.poll() is not None:
        cmd = ["python3", RS485_PROG, "--port", RS485_PORT, "--id", RS485_ID]
        _rs485 = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,  # no spam on stdout
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1
        )

def _rs485_send(line: str):
    """Invia una riga di comando a KMT_RS485 (es. 'ON 1')."""
    try:
        _rs485_start()
        _rs485.stdin.write(line.strip() + "\n")
        _rs485.stdin.flush()
    except Exception as e:
        logger.error(f"RS485 error: {e}")
        print("RS485 error:", e)

def rs485_on(ch: str):
    """Accende uno o più relè: ch = '1' oppure '1,3,5' oppure 'ALL'."""
    _rs485_send(f"ON {ch}")

def rs485_off(ch: str):
    """Spegne uno o più relè."""
    _rs485_send(f"OFF {ch}")

def rs485_off_all():
    """Spegne tutti i relè della scheda RS485."""
    _rs485_send("OFF A")

@atexit.register
def _rs485_cleanup():
    """Tenta di chiudere in modo pulito all'uscita."""
    try:
        if _rs485 and _rs485.poll() is None:
            # modo pulito: invia EXIT se supportato, altrimenti termina
            try:
                _rs485_send("EXIT")
            except Exception:
                pass
            _rs485.terminate()
    except Exception:
        pass
# ==============================================================

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

rel1 = GPIO_conf("pioA13", chipA, "Rel1", "out", 0)
rel2 = GPIO_conf("pioA14", chipA, "Rel2", "out", 0)
ledGreen = GPIO_conf("pioD26", chipD, "led_green", "out", 1)
ledRed = GPIO_conf("pioD14", chipD, "led_red", "out", 1)
rgbRed = GPIO_conf("pioD19", chipD, "RGB_red", "out", 1)
rgbGreen = GPIO_conf("pioD31", chipD, "RGB_green", "out", 1)
rgbBlue = GPIO_conf("pioD30", chipD, "RGB_blue", "out", 1)
digOut1 = GPIO_conf("pioC13", chipC, "DIG_OUT1", "out", 0)
digOut2 = GPIO_conf("pioC12", chipC, "DIG_OUT2", "out", 0)
pcieOn = GPIO_conf("pioC20", chipC, "PCIe_ON", "out", 0)
digIn1 = GPIO_conf("pioA15", chipA, "DIG_IN1", "in")
digIn2 = GPIO_conf("pioC14", chipC, "DIG_IN2", "in")

# =========================
# Safe wrapper per send_dataLW
# =========================
class SafeEBI(EBI):
    def safe_send_dataLW(self, payload, dst=None):
        try:
            ret = self.send_dataLW(payload=payload, dst=dst)
            if ret is None:
                logger.warning("send_dataLW ha restituito None (nessuna risposta dal modulo)")
                return {"status": "NoResponse"}
            return ret
        except Exception as e:
            logger.error(f"Errore in send_dataLW: {e}")
            return {"status": "Exception", "error": str(e)}

class DeviceController:
    def __init__(self, shell, rel1, rel2, ledGreen, ledRed, rgbRed, rgbGreen, rgbBlue, digOut1, digOut2, pcieOn, digIn1, digIn2):
        self.shell = shell
        self.rel1 = rel1
        self.rel2 = rel2
        self.ledGreen = ledGreen
        self.ledRed = ledRed
        self.rgbRed = rgbRed
        self.rgbGreen = rgbGreen
        self.rgbBlue = rgbBlue
        self.digOut1 = digOut1
        self.digOut2 = digOut2
        self.pcieOn = pcieOn
        self.digIn1 = digIn1
        self.digIn2 = digIn2

    def rel(self, relN, relState='OFF'):
        state = 1 if relState == 'ON' else 0
        if(relN=='1'):
            self.rel1.set_values([state])
        elif(relN=='2'):
            self.rel2.set_values([state])
        else:
            # se il numero non è valido → spegne entrambi
            self.rel1.set_values([0])
            self.rel2.set_values([0])
            relN = 'ERR'
            relState = 'INVALID'

        # Feedback LoRaWAN uplink
        self.shell.do_send("T:R;N:" + relN + ";S:" + relState)
        if self.shell._e.debug:
            print(Fore.RED + "T:R;N:" + relN + ";S:" + relState)
            print("Relay end" + Style.RESET_ALL)
        
    relxs = ['A', '1', '2', '3', '4', '5', '6', '7', '8']
    def relX(self, relXN, relXState='OFF'):
        """Gestione dei relè esterni su RS485"""
        if(relXN not in self.relxs):
            #print("RelX not recognized")
            return
        if(relXState == 'ON'):
            rs485_on(relXN)
        elif(relXState == 'OFF'):
            rs485_off(relXN)
        # Feedback LoRaWAN uplink
        self.shell.do_send("T:X;N:" + relXN + ";S:" + relXState)
        if self.shell._e.debug:
            print(Fore.RED + "T:X;N:" + relXN + ";S:" + relXState)
            print("RS485 end" + Style.RESET_ALL)

    leds = ['r','g','R','G','B']
    def led(self, led, ledState='OFF'):
        state = 0 if ledState == 'ON' else 1 #Active low

        if(led=='g'):
            self.ledGreen.set_values([state])
        elif(led=='r'):
            self.ledRed.set_values([state])
        elif(led=='R'):
            self.rgbRed.set_values([state])
        elif(led=='G'):
            self.rgbGreen.set_values([state])
        elif(led=='B'):
            self.rgbBlue.set_values([state])
        else:
            self.ledRed.set_values([1])
            self.ledGreen.set_values([1])
            self.rgbRed.set_values([1])
            self.rgbGreen.set_values([1])
            self.rgbBlue.set_values([1])
        self.shell.do_send("T:L;N:" + led + ";S:" + ledState)
        if self.shell._e.debug:
            print(Fore.RED + "T:L;N:" + led + ";S:" + ledState)
            print("LED end" + Style.RESET_ALL)


    digs = ['P', '1', '2']
    """Gestione delle uscite digitali"""
    def dig(self, digN, digStatus):
        state = 1 if digStatus == 'ON' else 0 
        if(digN=='P'):
            self.pcieOn.set_values([state])
        elif(digN=='1'):
            self.digOut1.set_values([state])
        elif(digN=='2'):
            self.digOut2.set_values([state])
        else:
            self.pcieOn.set_values([0])
            self.digOut1.set_values([0])
            self.digOut2.set_values([0])
        self.shell.do_send("T:D;N:" + digN + ";S:" + digStatus)
        if self.shell._e.debug:
            print(Fore.RED + "T:D;N:" + digN + ";S:" + digStatus)
            print("Digs end" + Style.RESET_ALL)


    def AllOFF(self):
        """Spegne tutte le periferiche"""
        self.rel1.set_values([0])
        self.rel2.set_values([0])
        self.ledGreen.set_values([1])
        self.ledRed.set_values([1])
        self.rgbRed.set_values([1])
        self.rgbGreen.set_values([1])
        self.rgbBlue.set_values([1])
        self.digOut1.set_values([0])
        self.digOut2.set_values([0])
        self.pcieOn.set_values([0])
        self.relX("A", "OFF")
        self.shell.do_send("T:A;N:A;S:OFF")

        if self.shell._e.debug:
            print(Fore.RED + "T:A;N:A;S:OFF")
            print("AllOFF end" + Style.RESET_ALL)

    def deviceSet(self, devType, devNum, devStatus):  
        """
        Decodifica del comando ricevuto e dispatch alla funzione corretta.
        device_type: R, X, L, D, A
        device_num: numero o identificativo (es. '1', '2', 'A')
        device_status: ON / OFF
        """
        if self.shell._e.debug:
                print(Fore.GREEN + "Parsed data: " )         
                print(devType, devNum, devStatus + Style.RESET_ALL)

        if devType == 'R':
            if devNum in ['1', '2']:
                if devStatus in ['ON', 'OFF']:
                    self.rel(devNum, devStatus)
                    """
                    if(devNum=='1'):
                        self.led('r',devStatus)
                    else:
                        self.led('g',devStatus)
                    """
                else:
                    if self.shell._e.debug:
                        print("Dev Status not recognized")
            else:
                if self.shell._e.debug:
                    print("Dev Num not recognized") 
        elif devType == 'X':
            if devNum in self.relxs:
                if devStatus in ['ON', 'OFF']:
                    self.relX(devNum, devStatus)
                else:
                    if self.shell._e.debug:
                        print("Dev Status not recognized")
            else:
                if self.shell._e.debug:
                    print("Dev Num not recognized")
        elif devType == 'L':
            if devNum in self.leds:
                if devStatus in ['ON', 'OFF']:
                    self.led(devNum, devStatus)
                else:
                    if self.shell._e.debug:
                        print("Dev Status not recognized")
            else:
                if self.shell._e.debug:
                    print("Dev Num not recognized") 
        elif devType == 'D':
            if devNum in self.digs:
                if devStatus in ['ON', 'OFF']:
                    self.dig(devNum, devStatus)
                else:
                    if self.shell._e.debug:
                        print("Dev Status not recognized")
            else:
                if self.shell._e.debug:
                    print("Dev Num not recognized") 
        else:
            if self.shell._e.debug:
                print("Dev Type not recognized")  

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

    def __init__(self, device, auto=None):
        self._e = SafeEBI(device)   # <--- uso la classe "sicura"

        # passo tutte le risorse hardware al controller
        self.controller = DeviceController(
            self,
            rel1, rel2,
            ledGreen, ledRed, rgbRed, rgbGreen, rgbBlue,
            digOut1, digOut2, pcieOn,
            digIn1, digIn2
        )

        self._e.reset()
        state = self._e.state
        self.intro = "EMBIT module {embit_module} - FW {firmware_version}\n".format(**state)
        if state['state'] == 'Online':
            self._e.network_stop()
        self._e.energy_save(0x00) # Always on
        self._params = { 'channel': 1, 'sf': 7, 'bw': 0, 'cr': 1 } # 868.100 MHz, 128 Chips/symbol, 125 kHz, 4/5
        self._e.operating_channel(*self._params.values())
        self._e.network_start()
        if(auto == 'A'):
            self.do_debug("1")
            self.do_auto()
        if(auto == 'B'):
            self.do_debug("0")
            self.do_auto()
        super().__init__()

    def default(self, line):
        if line == "EOF":
            if self._e.debug:
                print("\nBye!")
            self.controller.AllOFF()
            return True
        return super().default(line)

    def do_debug(self, status=None):
        """set debug mode
Usage: debug 0 or 1"""
        if(status == "0"):
            self._e.debug = False
        if(status == "1"):
            self._e.debug = True        
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
 
    def do_uart(self, arg):
        """get or set device serial communication
Usage: uart [value]

value: [0-256]"""
        value = None
        if arg:
            try:
                value = int(arg) % 256
            except ValueError:
                if self._e.debug:
                    print("Invalid UART value {}".format(arg))
                return
        state = self._e.device_state()
        should_stop = value and state['state'] == 'Online'
        if should_stop:
            self._e.network_stop()
        ret = self._e.uart(value)
        if should_stop:
            self._e.network_start()
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
            print(payload, dst)
        if dst is not None:
            try:
                dst = int(dst)
                dst = [ (dst & 0xFF00) >> 8, dst & 0x00FF ]
            except ValueError:
                print("Invalid destination value {}".format(dst))
                return
        ret = self._e.safe_send_dataLW(payload=payload, dst=dst)  # <--- uso safe
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
        if RSSI:
            #self.controller.led('R', 'ON')

            if self._e.debug:
                print(Fore.GREEN + "Received data: " )
                print("RSSI:" , RSSI, " - FPort: ", FPort, " - Data: ", data + Style.RESET_ALL)
            
            dataSplit=data.split(":")
            self.controller.deviceSet(dataSplit[0], dataSplit[1], dataSplit[2])
            #time.sleep(0.5)
            #self.controller.led('R', 'OFF')
        else:
            if self._e.debug:
                print ("\r", strftime("%H:%M:%S", localtime()), end='' )

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

    def do_auto(self):
        """Put the module in continuos receive
Usage: auto

value: []"""
        self.do_lorawan(0)
        if self._e.debug:
            print('RX loop')  
        self.do_send('T:OK;N:OK;S:OK')   
        while(1):   
            self.do_receive()
            
    def do_quit(self, arg):
            """quit EMB shell
    Usage: quit"""
            if self._e.debug:
                print("\nBye!")
            self.controller.AllOFF()
            return True

if __name__ == '__main__':
    #Avvio processo RS485==============
    _rs485_start()  # avvio subito all'inizio
    
    device = "/dev/ttyS6"
    auto = None

    n = len(sys.argv)
    if n > 1:
        auto = sys.argv[1]
        if((auto == "A") or (auto == "B")):
            print("OK")
        else:
            print('Parameter error')
            print('Input nothing, A for auto receive or B for auto receive without debug')
            exit()
    if n > 2:
        device = sys.argv[2]

    shell = EmbitShell(device, auto)
    shell.controller.AllOFF()

    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        print("\nBye!")
        shell.controller.AllOFF()