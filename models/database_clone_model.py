from datetime import datetime


class DatabaseCloneModel:
    source_instance_name: str
    destination_instance_name: str
    point_in_time: datetime
