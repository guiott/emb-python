#!/usr/bin/env python3
import serial, time, argparse, threading, sys

# Colori terminale
class Colors:
    ON = '\033[92m'   # Verde
    OFF = '\033[91m'  # Rosso
    AUTO_OFF = '\033[93m'  # Giallo
    END = '\033[0m'

class KMTronicRelay:
    def __init__(self, port='/dev/ttyS4', baudrate=9600, board_id=1, timeout=1):
        self.ser = serial.Serial(port, baudrate, bytesize=8, parity='N', stopbits=1, timeout=timeout)
        self.board_id = board_id
        self.lock = threading.Lock()
        self.auto_off_channels = set()  # tiene traccia dei relè spenti automaticamente

    def _cmd_bytes(self, channel, on=True):
        if not (1 <= channel <= 8):
            raise ValueError('Channel must be 1-8')
        return bytes([0xFF, channel, 0x01 if on else 0x00])

    def set_relay(self, channels, on=True, duration=None, timers_list=None, status_callback=None):
        if isinstance(channels, int):
            channels = [channels]
        with self.lock:
            for ch in channels:
                self.ser.write(self._cmd_bytes(ch, on))
                if not on and ch in self.auto_off_channels:
                    self.auto_off_channels.discard(ch)
        time.sleep(0.1)

        if duration is not None and on:
            t = threading.Thread(target=self._timer_off, args=(channels, duration, status_callback))
            t.start()
            if timers_list is not None:
                timers_list.append(t)

    def _timer_off(self, channels, duration, status_callback):
        time.sleep(duration)
        with self.lock:
            for ch in channels:
                self.ser.write(self._cmd_bytes(ch, False))
                self.auto_off_channels.add(ch)
        if status_callback is not None:
            try:
                st = self.get_status()
                status_callback(st, auto_off=True)
            except:
                pass

    def get_status(self):
        cmd = bytes([0xFF, 0xA1 + (self.board_id - 1), 0x00])
        with self.lock:
            self.ser.write(cmd)
            resp = self.ser.read(8)
        if len(resp) != 8:
            raise IOError('Read incomplete status: got %d bytes' % len(resp))
        return {i+1: (resp[i] == 1) for i in range(8)}

    def close(self):
        self.ser.close()

def format_status(st, use_color=True, auto_off_channels=set()):
    parts = []
    for ch, val in st.items():
        if val:
            s = 'ON'
            color = Colors.ON if use_color else ''
        else:
            if ch in auto_off_channels:
                s = 'OFF'
                color = Colors.AUTO_OFF if use_color else ''
            else:
                s = 'OFF'
                color = Colors.OFF if use_color else ''
        if use_color:
            s = f"{color}{s}{Colors.END}"
        parts.append(f"{ch}:{s}")
    return ' '.join(parts)

def parse_channels(ch_str):
    if ch_str.upper() == 'A':
        return list(range(1,9))
    return [int(x) for x in ch_str.split(',')]


def status_updater(relay, use_color):
    while True:
        try:
            st = relay.get_status()
            if st != relay.last_status:
                print("\n[Auto Status] " + format_status(st, use_color))
                relay.last_status = st
        except:
            pass
        time.sleep(1)  # Controlla ogni secondo


def main():
    parser = argparse.ArgumentParser(description='KMTronic RS485 Relay controller')
    parser.add_argument('--port', default='/dev/ttyS4')
    parser.add_argument('--id', type=int, default=1)
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--nocolor', action='store_true')
    parser.add_argument('--compact','-c', action='store_true')
    args = parser.parse_args()

    relay = KMTronicRelay(port=args.port, board_id=args.id)
    use_color = not args.nocolor
    timers_list = []

    def show_status(st, auto_off=False):
        print(format_status(st, use_color, relay.auto_off_channels))
    
    # Thread di aggiornamento automatico dello status in interattivo
    if sys.stdin.isatty():
        t = threading.Thread(target=status_updater, args=(relay, use_color), daemon=True)
        t.start()

    try:
        while True:
            if sys.stdin.isatty():
                cmd = input('Relay> ').strip()
            else:
                cmd = sys.stdin.readline()
                if not cmd:
                    break
                cmd = cmd.strip()
            if not cmd:
                continue
            parts = cmd.split()
            action = parts[0].upper()
            if action == 'EXIT':
                break
            elif action == 'HELP':
                print("Commands:\n  ON <ch[,ch,...]|A> [-t seconds]\n  OFF <ch[,ch,...]|A>\n  STATUS\n  HELP\n  EXIT")
                continue
            elif action == 'STATUS':
                try:
                    st = relay.get_status()
                    print(format_status(st, use_color, relay.auto_off_channels))
                except Exception as e:
                    print("Error reading status:", e)
                continue
            elif action in ['ON','OFF']:
                if len(parts)<2:
                    print("Specify channels")
                    continue
                ch_str = parts[1]
                channels = parse_channels(ch_str)
                duration = None
                if '-t' in parts:
                    try:
                        t_index = parts.index('-t')
                        duration = float(parts[t_index+1])
                    except:
                        print("Invalid -t value")
                        continue
                relay.set_relay(channels, on=(action=='ON'), duration=duration, timers_list=timers_list,
                                status_callback=show_status if (args.verbose or sys.stdin.isatty()) else None)
                if args.verbose or sys.stdin.isatty():
                    try:
                        st = relay.get_status()
                        print(format_status(st, use_color, relay.auto_off_channels))
                    except:
                        pass
            else:
                print("Unknown command. Type HELP.")

        # Se input da pipe, attendi tutti i timer
        for t in timers_list:
            t.join()

    finally:
        relay.close()

if __name__ == '__main__':
    main()