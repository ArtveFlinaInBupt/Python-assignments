#! /usr/bin/env python3
# -*- coding: utf-8 -*-


import json
import os
from tkinter.scrolledtext import ScrolledText
from tkinter.filedialog import asksaveasfilename
from tkinter import ttk
from typing import Dict, List, Literal, Optional, Tuple, Union

import aiohttp
import asyncio
import pyperclip # type: ignore
import tkinter as tk
import xml.dom.minidom


def unify_crlf(s: str) -> str:
    return os.linesep.join([s for s in s.splitlines() if s.strip()])


class WeatherDataEntry:
    def __init__(
        self, year: int, temperature: float, temperature_smoothed: float
    ) -> None:
        self.year: int = year
        self.temperature: float = temperature
        self.temperature_smoothed: float = temperature_smoothed

    @classmethod
    def try_from(
        cls, year: str, temperature: str, temperature_smoothed: str
    ) -> 'WeatherDataEntry':
        try:
            return cls(
                int(year), float(temperature), float(temperature_smoothed)
            )
        except ValueError as e:
            raise Exception(f'Invalid weather data entry {e}')

    def __str__(self) -> str:
        return f'{self.year} {self.temperature} {self.temperature_smoothed}'


class WeatherData:
    class Params:
        def __init__(
            self, lower: int, upper: int,
            order: Optional[Literal['asc', 'desc']] = None,
        ) -> None:
            self.lower: int = lower
            self.upper: int = upper
            self.order: Optional[str] = order

        @classmethod
        def try_from(
            cls, lower: str, upper: str, order: str
        ) -> 'WeatherData.Params':
            try:
                lower_: int = int(lower)
                upper_: int = int(upper)
                order_: Optional[Literal['asc', 'desc']] = None
                if order in ('asc', 'desc'):
                    order_ = order # type: ignore
                elif len(order) != 0:
                    raise ValueError(f'Order cannot be {order}')
            except ValueError as e:
                raise Exception(f'Invalid params: {e}')

            return cls(lower_, upper_, order_)

        def to_dict(self) -> Dict[str, Union[int, str]]:
            return {
                'lower': self.lower, 'upper': self.upper, 'order': self.order
            } if self.order else {'lower': self.lower, 'upper': self.upper}

    def __init__(self, data: Optional[List[WeatherDataEntry]] = None) -> None:
        self.data: List[WeatherDataEntry] = data if data else []

    def append(self, entry: WeatherDataEntry) -> None:
        self.data.append(entry)

    def __str__(self) -> str:
        return 'year temperature temperature_smoothed\n' + \
            '\n'.join(str(entry) for entry in self.data)

    @classmethod
    def from_json(cls, json_obj: str) -> 'WeatherData':
        ret: 'WeatherData' = cls()
        for entry in json.loads(json_obj):
            ret.append(WeatherDataEntry(
                entry['year'],
                entry['temperature'],
                entry['temperature_smoothed'])
            )
        return ret

    @classmethod
    def from_csv(cls, csv_obj: str) -> 'WeatherData':
        ret: 'WeatherData' = cls()
        for entry in csv_obj.splitlines():
            year, temperature, temperature_smoothed = entry.split(',')
            if year == 'year':
                continue
            ret.append(WeatherDataEntry.try_from(
                year, temperature, temperature_smoothed)
            )
        return ret

    @classmethod
    def from_xml(cls, xml_obj: str) -> 'WeatherData':
        ret: 'WeatherData' = cls()
        for entry in xml.dom.minidom.parseString(xml_obj) \
                .getElementsByTagName('entry'):
            ret.append(WeatherDataEntry.try_from(
                # autopep8: off
                entry.getElementsByTagName('year')[0] \
                    .firstChild.data, # type: ignore
                entry.getElementsByTagName('temperature')[0] \
                    .firstChild.data, # type: ignore
                entry.getElementsByTagName('temperature_smoothed')[0] \
                    .firstChild.data, # type: ignore
                # autopep8: on
            ))
        return ret


class QueryType:
    VALUES = ['/json', '/csv', '/xml']

    def __init__(self, type: str) -> None:
        if type not in self.VALUES:
            raise Exception('Invalid query type')
        self.type = type


async def fetch_data(
    server: str, query_type: QueryType, params: WeatherData.Params
) -> Tuple[str, str]:
    url = server + query_type.type

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params.to_dict()) as response:
            if response.status != 200:
                raise Exception(
                    'Failed to fetch data from '
                    f'{url} {response.status} {response.reason}'
                )

            raw: Optional[str] = None
            pretty: Optional[str] = None
            decoded: Optional[WeatherData] = None

            if query_type.type == '/json':
                raw = await response.text()
                pretty = json.dumps(json.loads(raw), indent=2)
                decoded = WeatherData.from_json(raw)
            elif query_type.type == '/csv':
                raw = await response.text()
                pretty = unify_crlf(raw)
                decoded = WeatherData.from_csv(raw)
            elif query_type.type == '/xml':
                raw = await response.text()
                pretty = unify_crlf(
                    xml.dom.minidom.parseString(raw).toprettyxml(indent='  ')
                )
                decoded = WeatherData.from_xml(raw)
            else:
                raise Exception(f'Failed to fetch data from {url}')

            return pretty, str(decoded)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title('Simple Weather Data Client')
        self.create_widgets()

    def create_widgets(self) -> None:
        # 服务器地址输入框
        self.label_request_type = tk.Label(self, text='服务器：')
        self.label_request_type.grid(
            row=0, column=1, padx=0, pady=10, sticky='E'
        )

        self.url_entry = tk.Entry(self, width=30)
        self.url_entry.insert(0, 'http://127.0.0.1:555')
        self.url_entry.grid(
            row=0, column=2, columnspan=4, padx=0, pady=10, sticky='EW'
        )

        # 查询按钮
        self.query_button = tk.Button(
            self, text='查询', width=5, command=self.perform_query
        )
        self.query_button.grid(row=0, column=7, padx=10, pady=0, sticky='E')

        # 下拉选择框
        self.label_request_type = tk.Label(self, text='查询类型：')
        self.label_request_type.grid(
            row=1, column=0, padx=0, pady=0, sticky='E'
        )

        self.request_type_combobox = ttk.Combobox(
            self, width=7, state='readonly'
        )
        self.request_type_combobox['values'] = QueryType.VALUES
        self.request_type_combobox.current(0)
        self.request_type_combobox.grid(
            row=1, column=1, padx=0, pady=0, sticky='W'
        )

        # 排序方式
        self.label_order = tk.Label(self, text='排序方式：')
        self.label_order.grid(row=1, column=2, padx=0, pady=0, sticky='E')

        self.order_combobox = ttk.Combobox(self, width=7, state='readonly')
        self.order_combobox['values'] = ['年份顺序', '温度升序', '温度降序']
        self.order_combobox.current(0)
        self.order_combobox.grid(row=1, column=3, padx=0, pady=0, sticky='W')

        # 起始年份
        self.label_lower = tk.Label(self, text='起始年份：')
        self.label_lower.grid(
            row=1, column=4, padx=0, pady=0, sticky='E'
        )

        self.lower_entry = tk.Entry(self, width=7)
        self.lower_entry.insert(0, '1900')
        self.lower_entry.grid(row=1, column=5, padx=0, pady=0, sticky='W')

        # 结束年份
        self.label_upper = tk.Label(self, text='结束年份：')
        self.label_upper.grid(row=1, column=6, padx=0, pady=0, sticky='E')

        self.upper_entry = tk.Entry(self, width=7)
        self.upper_entry.insert(0, '2020')
        self.upper_entry.grid(row=1, column=7, padx=0, pady=0, sticky='W')

        # 原始数据显示区域
        self.result_raw = ScrolledText(
            self, height=40, width=55, state='disabled')
        self.result_raw.grid(
            row=2, column=0, columnspan=4, padx=5, pady=0, sticky='NSEW'
        )

        # 文本显示区域
        self.result_text = ScrolledText(
            self, height=40, width=55, state='disabled')
        self.result_text.grid(
            row=2, column=4, columnspan=4, padx=5, pady=0, sticky='NSEW'
        )

        # 保存原始数据按钮
        self.save_raw_button = tk.Button(
            self, text='保存原始数据', width=7, command=self.save_raw
        )
        self.save_raw_button.grid(
            row=3, column=0, padx=10, pady=10, sticky='W'
        )

        # 原始数据动作回显
        self.raw_action_label = tk.Label(self, text='')
        self.raw_action_label.grid(
            row=3, column=1, columnspan=2, padx=10, pady=10
        )

        # 复制原始数据到剪贴板按钮
        self.copy_raw_button = tk.Button(
            self, text='复制到剪贴板', width=7, command=self.copy_raw_to_clipboard
        )
        self.copy_raw_button.grid(
            row=3, column=3, padx=10, pady=10, sticky='E')

        # 保存解码后文本按钮
        self.save_text_button = tk.Button(
            self, text='保存解析文本', width=7, command=self.save_text)
        self.save_text_button.grid(
            row=3, column=4, padx=10, pady=10, sticky='W'
        )

        # 动作回显
        self.text_action_label = tk.Label(self, text='')
        self.text_action_label.grid(
            row=3, column=5, columnspan=2, padx=10, pady=10)

        # 复制文本到剪贴板按钮
        self.copy_button = tk.Button(
            self, text='复制到剪贴板', width=7, command=self.copy_text_to_clipboard
        )
        self.copy_button.grid(row=3, column=7, padx=10, pady=10, sticky='E')

    def empty_raw_action_label(self) -> None:
        self.raw_action_label.config(text='')

    def empty_text_action_label(self) -> None:
        self.text_action_label.config(text='')

    def perform_query(self) -> None:
        raw: Optional[str] = None
        text: Optional[str] = None

        try:
            server_url: str = self.url_entry.get().rstrip('/')
            query_type: QueryType = QueryType(self.request_type_combobox.get())
            params = WeatherData.Params.try_from(
                self.lower_entry.get(),
                self.upper_entry.get(),
                {'年份顺序': '', '温度升序': 'asc', '温度降序': 'desc'}.get(
                    self.order_combobox.get(), ''
                )
            )
            raw, text = asyncio.run(fetch_data(server_url, query_type, params))
        except Exception as e:
            raw = f'Failed to fetch data: {e}'
            text = ''

        self.result_raw.config(state='normal')
        self.result_raw.delete('1.0', tk.END)
        self.result_raw.insert(tk.END, raw)
        self.result_raw.config(state='disabled')

        self.result_text.config(state='normal')
        self.result_text.delete('1.0', tk.END)
        self.result_text.insert(tk.END, text)
        self.result_text.config(state='disabled')

    def save_raw(self) -> None:
        query_type: QueryType = QueryType(self.request_type_combobox.get())
        default_extension: str = {
            '/json': '.json', '/csv': '.csv', '/xml': '.xml'
        }.get(query_type.type, 'txt')
        file_type: Tuple[str, str] = {
            '/json': ('JSON Files', '*.json'),
            '/csv': ('CSV Files', '*.csv'),
            '/xml': ('XML Files', '*.xml'),
        }.get(query_type.type, ('Text Files', '*.txt'))
        file_path = asksaveasfilename(
            defaultextension=default_extension,
            filetypes=[file_type, ('All Files', '*.*')],
            initialdir=os.getcwd()
        )
        if file_path:
            with open(file_path, 'w') as f:
                f.write(self.result_raw.get('1.0', tk.END))
            self.raw_action_label.config(text=f'已保存到{file_path}')
            self.after(5000, self.empty_raw_action_label)

    def save_text(self) -> None:
        file_path = asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('Text Files', '*.txt'), ('All Files', '*.*')],
            initialdir=os.getcwd()
        )
        if file_path:
            with open(file_path, 'w') as f:
                f.write(self.result_text.get('1.0', tk.END))
            self.text_action_label.config(text=f'已保存到{file_path}')
            self.after(5000, self.empty_text_action_label)

    def copy_raw_to_clipboard(self) -> None:
        pyperclip.copy(self.result_raw.get('1.0', tk.END))
        self.raw_action_label.config(text='已复制到剪贴板')
        self.after(5000, self.empty_raw_action_label)

    def copy_text_to_clipboard(self) -> None:
        pyperclip.copy(self.result_text.get('1.0', tk.END))
        self.text_action_label.config(text='已复制到剪贴板')
        self.after(5000, self.empty_text_action_label)


if __name__ == '__main__':
    app = App()
    app.mainloop()
