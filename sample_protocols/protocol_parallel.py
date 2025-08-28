from datetime import timedelta

from src.protocol import Delay, FromType, Protocol, Start

# Protocols
getimage_1_1 = Protocol(name="getimage_plate6well_Co2Incubator#1#1")
getimage_1_2 = Protocol(name="getimage_plate6well_Co2Incubator#1#2")
getimage_1_3 = Protocol(name="getimage_plate6well_Co2Incubator#1#3")
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
offset = -timedelta(seconds=0)
delay_15min = Delay(
    duration=timedelta(seconds=15), from_type=FromType.FINISH, offset=offset
)
delay_30min = Delay(
    duration=timedelta(seconds=30), from_type=FromType.FINISH, offset=offset
)
delay_60min = Delay(
    duration=timedelta(seconds=60), from_type=FromType.FINISH, offset=offset
)
delay_90min = Delay(
    duration=timedelta(seconds=90), from_type=FromType.FINISH, offset=offset
)
delay_180min = Delay(
    duration=timedelta(seconds=180), from_type=FromType.FINISH, offset=offset
)
delay_240min = Delay(
    duration=timedelta(seconds=240), from_type=FromType.FINISH, offset=offset
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
    > move_tube_1p5mL_Freezer_24_LifterStocker_12_12
    > [
        min_0_collection,
        min_5_collection,
        min_15_collection_first_half,
        min_30_collection_first_half,
        min_60_collection_first_half,
        min_90_collection_first_half,
        min_180_collection_first_half,
        min_240_collection_first_half,
    ]
)

min_15_collection_first_half > delay_15min > min_15_collection_second_half
min_30_collection_first_half > delay_30min > min_30_collection_second_half
min_60_collection_first_half > delay_60min > min_60_collection_second_half
min_90_collection_first_half > delay_90min > min_90_collection_second_half
min_180_collection_first_half > delay_180min > min_180_collection_second_half
min_240_collection_first_half > delay_240min > min_240_collection_second_half
