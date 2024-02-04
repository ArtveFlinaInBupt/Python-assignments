#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from io import StringIO
from sanic import Sanic, response
from sanic.config import Config
from sanic.request import Request
from sanic.response import HTTPResponse
from typing import Any, Dict, List, Literal, Optional, Union

import csv
import os
import shutil


# ------------------ utilities ------------------


def dict_to_xml(data: Dict[str, Any]) -> str:
    xml: str = ''
    for key, value in data.items():
        xml += f'<{key}>{value}</{key}>'
    return xml


def try_remove(path: str) -> None:
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.isfile(path):
            os.remove(path)
    except FileNotFoundError:
        pass


# ------------------ data ------------------


class WeatherDataEntry:
    def __init__(
            self, year: int, temperature: float, temperature_smoothed: float
    ) -> None:
        self.year: int = year
        self.temperature: float = temperature
        self.temperature_smoothed: float = temperature_smoothed

    def to_dict(self) -> Dict[str, Union[int, float]]:
        return {
            'year': self.year,
            'temperature': self.temperature,
            'temperature_smoothed': self.temperature_smoothed
        }


class WeatherData:
    def __init__(self, data: Optional[List[WeatherDataEntry]] = None) -> None:
        self.data: List[WeatherDataEntry] = data if data else []

    def append(self, entry: WeatherDataEntry) -> None:
        self.data.append(entry)

    class Params:
        def __init__(
                self, lower: int, upper: int, order: Optional[Literal['asc', 'desc']] = None
        ) -> None:
            self.lower: int = lower
            self.upper: int = upper
            self.order: Optional[str] = order

    def query(self, params: Params) -> List[WeatherDataEntry]:
        if params.order == None:
            return sorted(list(filter(
                lambda x: params.lower <= x.year <= params.upper, self.data
            )), key=lambda x: x.year)

        return sorted(filter(
            lambda x: params.lower <= x.year <= params.upper, self.data
        ), key=lambda x: x.temperature, reverse=params.order == 'desc')

    def query_dict(
            self, params: Params
    ) -> List[Dict[str, Union[int, float]]]:
        return list(map(WeatherDataEntry.to_dict, self.query(params)))


def load_data_from_file(file_name: str) -> WeatherData:
    data: WeatherData = WeatherData()

    with open(file_name, 'r') as f:
        lines: List[str] = f.readlines()
        for line in lines:
            if line.startswith('#') or line == '\n':
                continue

            year, temperature, temperature_smoothed = line.split()
            data.append(WeatherDataEntry(
                int(year), float(temperature), float(temperature_smoothed)
            ))

    return data


# ------------------ app [config] ------------------


class AppConfig(Config):
    WEATHER_DATA_SRC_FILE: str
    WEATHER_DATA: WeatherData
    INSTANCE_DIR: str
    CACHE_DIR: str

    def __init__(self, **kwargs: str) -> None:
        super().__init__()

        self.INSTANCE_DIR = kwargs['INSTANCE_DIR']
        try_remove(self.INSTANCE_DIR)
        os.makedirs(self.INSTANCE_DIR, exist_ok=True)

        self.CACHE_DIR = kwargs['CACHE_DIR']
        try_remove(self.CACHE_DIR)
        os.makedirs(self.CACHE_DIR, exist_ok=True)

        self.WEATHER_DATA_SRC_FILE = kwargs['WEATHER_DATA_SRC_FILE']
        self.WEATHER_DATA = load_data_from_file(self.WEATHER_DATA_SRC_FILE)


WEATHER_DATA_SRC_FILE: str = './graph.txt'
INSTANCE_DIR: str = './instance'
CACHE_DIR = INSTANCE_DIR + '/cache'

app: Sanic = Sanic(
    'SimpleWeatherDataServer',
    config=AppConfig(
        WEATHER_DATA_SRC_FILE=WEATHER_DATA_SRC_FILE,
        INSTANCE_DIR=INSTANCE_DIR,
        CACHE_DIR=CACHE_DIR
    ),
)


# ------------------ app [api] ------------------


def extract_get_params(request: Request) -> WeatherData.Params:
    lower_year: int = int(request.args['lower'][0])
    upper_year: int = int(request.args['upper'][0])
    order: Optional[str] = request.args.get('order')
    if order is not None and order not in ('asc', 'desc'):
        raise ValueError(
            f'Invalid order: {order}, must be either "asc" or "desc"'
        )

    return WeatherData.Params(lower_year, upper_year, order)


@app.get('/ping')
async def ping_handler(request: Request) -> HTTPResponse:
    arg: str = request.args.get('arg', 'ping')
    return response.text(arg.replace('i', 'o').replace('I', 'O'))


@app.get('/json')
async def get_json_handler(request: Request) -> HTTPResponse:
    params: Optional[WeatherData.Params] = None

    try:
        params = extract_get_params(request)
    except Exception as e:
        return response.json({'message': f'Invalid query: {e}'}, status=400)

    try:
        return response.json(app.config.WEATHER_DATA.query_dict(params))
    except Exception as e:
        return response.json({'message': f'Interal error: {e}'}, status=500)


@app.get('/csv')
async def get_csv_handler(request: Request) -> HTTPResponse:
    params: Optional[WeatherData.Params] = None

    try:
        params = extract_get_params(request)
    except Exception as e:
        return response.json({'message': f'Invalid query: {e}'}, status=400)

    try:
        output_stream = StringIO()
        writer = csv.writer(output_stream)
        writer.writerow(['year', 'temperature', 'temperature_smoothed'])
        for entry in app.config.WEATHER_DATA.query(params):
            writer.writerow([
                entry.year, entry.temperature, entry.temperature_smoothed
            ])
        return response.text(
            output_stream.getvalue(), content_type='text/csv'
        )

    except Exception as e:
        return response.json({'message': f'Interal error: {e}'}, status=500)


@app.get('/xml')
async def get_xml_handler(request: Request) -> HTTPResponse:
    params: Optional[WeatherData.Params] = None

    try:
        params = extract_get_params(request)
    except Exception as e:
        return response.json({'message': f'Invalid query: {e}'}, status=400)

    try:
        data = app.config.WEATHER_DATA.query(params)

        xml = '<?xml version="1.0" encoding="UTF-8"?>'
        xml += '<data>'
        for entry in data:
            xml += '<entry>'
            xml += dict_to_xml(entry.to_dict())
            xml += '</entry>'
        xml += '</data>'
        return response.text(xml, content_type='text/xml')

    except Exception as e:
        return response.json({'message': f'Interal error: {e}'}, status=500)


if __name__ == '__main__':
    app.run(port=555, debug=True)
