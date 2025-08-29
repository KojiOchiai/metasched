from datetime import timedelta

from src.protocol import Delay, FromType, Protocol, Start

# Protocols
getimage = Protocol(name="scheduling_1")
stimulation = Protocol(name="scheduling_2")
dissolution = Protocol(name="scheduling_3")
collection = Protocol(name="scheduling_4")
division = Protocol(name="scheduling_5")

# Delays
offset = -timedelta(minutes=0, seconds=0)
delay_3min = Delay(
    duration=timedelta(minutes=3), from_type=FromType.FINISH, offset=offset
)
delay_5min = Delay(
    duration=timedelta(minutes=5), from_type=FromType.FINISH, offset=offset
)
delay_10min = Delay(
    duration=timedelta(minutes=10), from_type=FromType.FINISH, offset=offset
)

# Start
start = Start()

# Relationship
## getimage
(
    start
    > getimage
    > stimulation
    > delay_10min
    > dissolution
    > delay_5min
    > collection
    > delay_3min
    > division
)

## preparation

## sampling
# (
#     getimage
#     > stimulation
#     > dissolution
#     > collection
#     > division
# )
#
# stimulation > delay_10min > dissolution
# dissolution > delay_5min > collection
# collection > delay_3min > division
