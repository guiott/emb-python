DESCRIPTION

This repo contains a few Python scripts for interacting with EMB-LR1276 modules from Embit.

- `ebi.py` is the main library; it's `__main__` method can serve both as demo and as test
- `sender.py`, `receiver.py` are two example scripts that rely on `ebi.py`
- `embitshell.py` is an interactive shell offering a simplified interaction with the module, it can be used for an interface between LoRaWAN and SBC local hardware.

This code has been written with the great help of Antonio Galea (https://github.com/ant9000) and ChatGPT

REQUIREMENTS

```pip install pyserial```

Please look at LoRaWANRemoteCommandSystem.md for a detailed description on using this for a complete system.