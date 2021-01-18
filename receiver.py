#!/usr/bin/python3

import sys
from ebi import EBI

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
    print("ENERGY SAVE -> ALWAYS ON:", e.energy_save(0x00))
    print("OPERATING CHANNEL -> CH 2 (868.300 MHz), SF 7, BW 125 kHz, CR 4/5:", e.operating_channel(2,7,0,1))
    print("NETWORK ADDRESS -> 00:02:", e.network_address([0,2]))
    print("NETWORK START:", e.network_start())
    while True:
        pkt = e.receive()
        if pkt:
            print('options: {options}, rssi: {rssi}, src: {src}, dst: {dst}, data:'.format(**pkt))
            print(pkt['data'])
