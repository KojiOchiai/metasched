from datetime import timedelta

from src.protocol import Delay, FromType, Protocol, Start

# Protocols
getimage_durataion = timedelta(seconds=20)
getimage_1_1 = Protocol(
    name="getimage_plate6well_Co2Incubator#1#1", duration=getimage_durataion
)
getimage_1_2 = Protocol(
    name="getimage_plate6well_Co2Incubator#1#2", duration=getimage_durataion
)
getimage_1_3 = Protocol(
    name="getimage_plate6well_Co2Incubator#1#3", duration=getimage_durataion
)
move_tube_1p5mL_Freezer_24_LifterStocker_12_12 = Protocol(
    name="move_tube1.5mL_Freezer#24_LifterStocker#12#12", duration=timedelta(seconds=10)
)

first_half_duration = timedelta(seconds=14)
second_half_duration = timedelta(seconds=30)
sec_0_collection = Protocol(
    name="0sec回収", duration=first_half_duration + second_half_duration
)
sec_5_collection = Protocol(
    name="5sec回収",
    duration=first_half_duration + timedelta(seconds=5) + second_half_duration,
)
sec_15_collection_first_half = Protocol(
    name="15sec回収_前半", duration=first_half_duration
)
sec_15_collection_second_half = Protocol(
    name="15sec回収_後半", duration=second_half_duration
)
sec_30_collection_first_half = Protocol(
    name="30sec回収_前半", duration=first_half_duration
)
sec_30_collection_second_half = Protocol(
    name="30sec回収_後半", duration=second_half_duration
)
sec_30_collection_second_half = Protocol(
    name="30sec回収_後半", duration=second_half_duration
)
sec_60_collection_first_half = Protocol(
    name="60sec回収_前半", duration=first_half_duration
)
sec_60_collection_second_half = Protocol(
    name="60sec回収_後半", duration=second_half_duration
)
sec_90_collection_first_half = Protocol(
    name="90sec回収_前半", duration=first_half_duration
)
sec_90_collection_second_half = Protocol(
    name="90sec回収_後半", duration=second_half_duration
)
sec_180_collection_first_half = Protocol(
    name="180sec回収_前半", duration=first_half_duration
)
sec_180_collection_second_half = Protocol(
    name="180sec回収_後半", duration=second_half_duration
)
sec_240_collection_first_half = Protocol(
    name="240sec回収_前半", duration=first_half_duration
)
sec_240_collection_second_half = Protocol(
    name="240sec回収_後半", duration=second_half_duration
)
EtOHwash1_LS_4_1 = Protocol(name="EtOHwash1_LS#4#1", duration=timedelta(seconds=10))

# Delays
offset = -timedelta(seconds=0)
delay_15sec = Delay(
    duration=timedelta(seconds=15), from_type=FromType.FINISH, offset=offset
)
delay_30sec = Delay(
    duration=timedelta(seconds=30), from_type=FromType.FINISH, offset=offset
)
delay_60sec = Delay(
    duration=timedelta(seconds=60), from_type=FromType.FINISH, offset=offset
)
delay_90sec = Delay(
    duration=timedelta(seconds=90), from_type=FromType.FINISH, offset=offset
)
delay_180sec = Delay(
    duration=timedelta(seconds=180), from_type=FromType.FINISH, offset=offset
)
delay_240sec = Delay(
    duration=timedelta(seconds=240), from_type=FromType.FINISH, offset=offset
)

# Start
start = Start()

# Relationship
(
    start
    > getimage_1_1
    > getimage_1_2
    > getimage_1_3
    > move_tube_1p5mL_Freezer_24_LifterStocker_12_12
    > [
        sec_0_collection,
        sec_5_collection,
        sec_15_collection_first_half,
        sec_30_collection_first_half,
        sec_60_collection_first_half,
        sec_90_collection_first_half,
        sec_180_collection_first_half,
        sec_240_collection_first_half,
    ]
)

# Time constrain
sec_15_collection_first_half > delay_15sec > sec_15_collection_second_half
sec_30_collection_first_half > delay_30sec > sec_30_collection_second_half
sec_60_collection_first_half > delay_60sec > sec_60_collection_second_half
sec_90_collection_first_half > delay_90sec > sec_90_collection_second_half
sec_180_collection_first_half > delay_180sec > sec_180_collection_second_half
sec_240_collection_first_half > delay_240sec > sec_240_collection_second_half
