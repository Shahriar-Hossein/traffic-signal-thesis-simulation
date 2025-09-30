# core/initializer.py
from models.traffic_signal import TrafficSignal, signals
import state
from core.cycle_fixed import fixed_traffic_cycle
from core.cycle_priority import control_traffic_cycle
from core.cycle_fairness_priority import fairness_control_traffic_cycle
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
    if state.currentMode == "priority":
        control_traffic_cycle()
    elif state.currentMode == "fairness_priority":
        fairness_control_traffic_cycle()
    else:
        fixed_traffic_cycle()
