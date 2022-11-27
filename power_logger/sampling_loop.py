from datetime import datetime
import time
from typing import List, Union

from influxdb_client import WritePrecision, InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from . import envoy
from .model import SampleData, PowerSample, EIMSample

class SamplingLoop:
    interval = 5

    def __init__(self, token: str, influxdb_url: str, influxdb_token: str, influxdb_org: str, influxdb_bucket:str) -> None:
        self.session_id = envoy.login(token)
        self.influxdb_url = influxdb_url
        self.influxdb_token = influxdb_token
        self.influxdb_org = influxdb_org
        self.influxdb_bucket = influxdb_bucket

    def run(self):
        while True:
            data = self.get_sample()
            self.write_to_influxdb(data)

    def get_sample(self) -> SampleData:
        # Determine how long until the next sample needs to be taken
        now = datetime.now()
        time_to_next = self.interval - (now.timestamp() % self.interval)

        # wait!
        time.sleep(time_to_next)

        data = envoy.get_power_data(self.session_id)

        return data

    def write_to_influxdb(self, data: SampleData) -> None:
        with InfluxDBClient(url=self.influxdb_url, token=self.influxdb_token, org=self.influxdb_org) as client:
            points = self.idb_points_from_sampledata(data)
            with client.write_api(write_options=SYNCHRONOUS) as write_api:
                write_api.write(bucket=self.influxdb_bucket, record=points)

    def idb_points_from_sampledata(self, data: SampleData) -> List[Point]:
        points = []
        for i, line in enumerate(data.total_consumption.lines):
            p = self.idb_point_from_powersample(f"consumption-line{i}", line)
            points.append(p)
        p = self.idb_point_from_powersample("consumption-total", data.total_consumption)
        points.append(p)

        for i, line in enumerate(data.total_production.lines):
            p = self.idb_point_from_powersample(f"production-line{i}", line)
            points.append(p)
        p = self.idb_point_from_powersample("production-total", data.total_production)
        points.append(p)

        for i, line in enumerate(data.net_consumption.lines):
            p = self.idb_point_from_powersample(f"net-line{i}", line)
            points.append(p)
        p = self.idb_point_from_powersample("net-total", data.net_consumption)
        points.append(p)

        return points

    def idb_point_from_powersample(self, name: str, data: Union[PowerSample, EIMSample]) -> Point:
        p = Point(name)
        p.time(data.ts, WritePrecision.S)
        p.tag("source", "power-meter")

        p.field("P", data.wNow)
        p.field("Q", data.reactPwr)
        p.field("S", data.apprntPwr)
        #p.field("pf", data.pwrFactor)

        if isinstance(data, PowerSample):
            p.field("I_rms", data.rmsCurrent)
            p.field("V_rms", data.rmsVoltage)

        return p
