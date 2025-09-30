# core/updater.py
from models.traffic_signal import signals
from config import noOfSignals

def update_signal_timers(current_green: int, yellow: bool):
    """
    Update signal countdowns each second.
    """
    for i in range(noOfSignals):
        if i == current_green:
            if yellow:
                signals[i].yellow -= 1
            else:
                signals[i].green -= 1
        else:
            signals[i].red = max(0, signals[i].red - 1)
