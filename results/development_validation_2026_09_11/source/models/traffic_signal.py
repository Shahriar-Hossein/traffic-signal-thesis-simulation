# traffic_signal.py

from typing import List

class TrafficSignal:
    def __init__(self, red: int, yellow: int, green: int):
        """
        Represents a traffic signal with red, yellow, and green durations.

        :param red: Duration of the red light
        :param yellow: Duration of the yellow light
        :param green: Duration of the green light
        """
        self.red = red
        self.yellow = yellow
        self.green = green
        self.signalText = ""

    def __repr__(self):
        return f"TrafficSignal(R={self.red}, Y={self.yellow}, G={self.green})"


# Global list that stores all traffic signal instances
signals: List[TrafficSignal] = []
