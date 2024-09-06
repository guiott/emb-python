#!/usr/bin/python3

import sys, time
from ebi import EBI
import codecs

#print(codecs.decode('1deadbeef4', 'hex'))

if __name__ == "__main__":
    device = "/dev/ttyUSB0"
    try:
        device = sys.argv[1]
    except:
        pass
    e = EBI(device, debug=True)
    print("RESET:", e.reset())
    print("STATE:", e.state)
    if e.state['state'] == 'Online':
        print("NETWORK STOP:", e.network_stop())
    print("ENERGY SAVE -> TX ONLY:", e.energy_save(0x02))
    print("OUTPUT POWER -> +13dBm:", e.output_power(13))
    print("OPERATING CHANNEL -> CH 2 (868.300 MHz), SF 7, BW 125 kHz, CR 4/5:", e.operating_channel(2,7,0,1))
    print("NETWORK START:", e.network_start())
    payload = [0x12, 0x12, 0x12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
    while True:
        print("SEND DATA %s:" % e.hex(payload), e.send_data(payload=payload))
        time.sleep(1)
    print("NETWORK STOP :", e.network_stop())
