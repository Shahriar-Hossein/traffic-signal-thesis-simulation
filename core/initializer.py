# core/initializer.py
from models.traffic_signal import TrafficSignal, signals
import state
from core.controllers import resolve
from config import (
    defaultRed, defaultYellow, defaultGreen
)
import time

def initialize():
    """
    Initialize the traffic signals with default values.
    """
    signals.clear()
    ts1 = TrafficSignal(0, defaultYellow, defaultGreen[0])
    ts2 = TrafficSignal(ts1.red + ts1.yellow + ts1.green, defaultYellow, defaultGreen[1])
    ts3 = TrafficSignal(defaultRed, defaultYellow, defaultGreen[2])
    ts4 = TrafficSignal(defaultRed, defaultYellow, defaultGreen[3])

    signals.extend([ts1, ts2, ts3, ts4])

    print(f"[DEBUG] state.currentMode = '{state.currentMode}'")
    # An unknown name raises rather than falling back to fixed: a silent
    # fallback would report fixed-24 results under another controller's name.
    resolve(state.currentMode)()
