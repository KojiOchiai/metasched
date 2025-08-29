from datetime import timedelta

from src.protocol import Delay, FromType, Protocol, Start

start = (
    Start()
    > Protocol(name="scheduling_1")
    > Protocol(name="scheduling_2")
    > Delay(duration=timedelta(minutes=10), from_type=FromType.FINISH)
    > Protocol(name="scheduling_3")
    > Delay(duration=timedelta(minutes=5), from_type=FromType.FINISH)
    > Protocol(name="scheduling_4")
    > Delay(duration=timedelta(minutes=3), from_type=FromType.FINISH)
    > Protocol(name="scheduling_5")
)
