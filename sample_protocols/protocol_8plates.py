from datetime import timedelta

from src.protocol import Delay, FromType, Protocol, Start

# Protocols
getimage_1_1 = Protocol(name="getimage_plate6well_Co2Incubator#1#1")
getimage_1_2 = Protocol(name="getimage_plate6well_Co2Incubator#1#2")
getimage_1_3 = Protocol(name="getimage_plate6well_Co2Incubator#1#3")
getimage_1_4 = Protocol(name="getimage_plate6well_Co2Incubator#1#4")
getimage_1_5 = Protocol(name="getimage_plate6well_Co2Incubator#1#5")
getimage_1_6 = Protocol(name="getimage_plate6well_Co2Incubator#1#6")
getimage_1_7 = Protocol(name="getimage_plate6well_Co2Incubator#1#7")
getimage_1_8 = Protocol(name="getimage_plate6well_Co2Incubator#1#8")
move_tube_1p5mL_Freezer_24_LifterStocker_12_12 = Protocol(
    name="move_tube1.5mL_Freezer#24_LifterStocker#12#12"
)
min_0_collection = Protocol(name="0min回収")
min_5_collection = Protocol(name="5min回収")
min_15_collection_first_half = Protocol(name="15min回収_前半")
min_15_collection_second_half = Protocol(name="15min回収_後半")
min_30_collection_first_half = Protocol(name="30min回収_前半")
min_30_collection_second_half = Protocol(name="30min回収_後半")
min_60_collection_first_half = Protocol(name="60min回収_前半")
min_60_collection_second_half = Protocol(name="60min回収_後半")
min_90_collection_first_half = Protocol(name="90min回収_前半")
min_90_collection_second_half = Protocol(name="90min回収_後半")
min_180_collection_first_half = Protocol(name="180min回収_前半")
min_180_collection_second_half = Protocol(name="180min回収_後半")
min_240_collection_first_half = Protocol(name="240min回収_前半")
min_240_collection_second_half = Protocol(name="240min回収_後半")
EtOHwash1_LS_4_1 = Protocol(name="EtOHwash1_LS#4#1")

# Delays
offset = -timedelta(minutes=9, seconds=11)
delay_15min = Delay(
    duration=timedelta(minutes=15), from_type=FromType.FINISH, offset=offset
)
delay_30min = Delay(
    duration=timedelta(minutes=30), from_type=FromType.FINISH, offset=offset
)
delay_60min = Delay(
    duration=timedelta(minutes=60), from_type=FromType.FINISH, offset=offset
)
delay_90min = Delay(
    duration=timedelta(minutes=90), from_type=FromType.FINISH, offset=offset
)
delay_180min = Delay(
    duration=timedelta(minutes=180), from_type=FromType.FINISH, offset=offset
)
delay_240min = Delay(
    duration=timedelta(minutes=240), from_type=FromType.FINISH, offset=offset
)

# Start
start = Start()

# Relationship
## getimage
(
    start
    > getimage_1_1
    > getimage_1_2
    > getimage_1_3
    > getimage_1_4
    > getimage_1_5
    > getimage_1_6
    > getimage_1_7
    > getimage_1_8
)

## preparation
getimage_1_8 > move_tube_1p5mL_Freezer_24_LifterStocker_12_12

## sampling
(
    move_tube_1p5mL_Freezer_24_LifterStocker_12_12
    > min_60_collection_first_half
    > min_0_collection
    > min_240_collection_first_half
)
(
    min_60_collection_second_half
    > min_5_collection
    > min_180_collection_first_half
    > min_30_collection_first_half
    > min_90_collection_first_half
)
(min_30_collection_second_half > min_15_collection_first_half)

min_15_collection_first_half > delay_15min > min_15_collection_second_half
min_30_collection_first_half > delay_30min > min_30_collection_second_half
min_60_collection_first_half > delay_60min > min_60_collection_second_half
min_90_collection_first_half > delay_90min > min_90_collection_second_half
min_180_collection_first_half > delay_180min > min_180_collection_second_half
min_240_collection_first_half > delay_240min > min_240_collection_second_half
