#! /usr/bin/env python3
# -*- coding: utf-8 -*-


from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from os import getenv
from tkinter.filedialog import askopenfilename
from typing import List, Optional

import matplotlib.pyplot as plt
import numpy as np
import sys
import tkinter as tk


def my_lowess(
    data_x: np.ndarray, data_y: np.ndarray, window_size: int
) -> np.ndarray:
    def w(x: float) -> float:
        return (1 - np.abs(x) ** 3) ** 3 if np.abs(x) <= 1 else 0

    def weighted_linear_regression(
        x: np.ndarray, y: np.ndarray, w: np.ndarray
    ) -> np.ndarray:
        w_sum = np.sum(w)
        x_mean = np.sum(x * w) / w_sum if w_sum != 0 else 0
        y_mean = np.sum(y * w) / w_sum if w_sum != 0 else 0
        x_diff: np.ndarray = x - x_mean
        y_diff: np.ndarray = y - y_mean
        b = np.sum(w * (x_diff * y_diff)) / np.sum(w * x_diff ** 2)
        a = y_mean - b * x_mean
        return a + b * x

    result: np.ndarray = np.zeros(len(data_y))
    for i in range(len(data_y)):
        start: int = i - window_size
        end: int = i + window_size + 1
        if start < 0:
            end -= start
            start = 0
        if end > len(data_y):
            start -= end - len(data_y)
            end = len(data_y)
        start = max(start, 0)
        end = min(end, len(data_y))

        window: np.ndarray = np.arange(start, end)
        x_local: np.ndarray = data_x[window]
        y_local: np.ndarray = data_y[window]
        result[i] = weighted_linear_regression(
            x_local - i,
            y_local,
            np.array([w(x) for x in (x_local - i) / max(abs(x_local - i))]),
        )[np.where(x_local == i)[0][0]]
    return result


def lowess(data_y: np.ndarray, windows_size: int) -> np.ndarray:
    if getenv('SM_LOWESS'):
        import statsmodels.api as sm
        return sm.nonparametric.lowess(
            data_y,
            np.arange(len(data_y)),
            frac=(2 * windows_size) / len(data_y),
        ).T[1]

    return my_lowess(np.arange(len(data_y)), data_y, windows_size)


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
    def __init__(self, data: Optional[List[WeatherDataEntry]] = None) -> None:
        self.data: List[WeatherDataEntry] = data if data else []

    def append(self, entry: WeatherDataEntry) -> None:
        self.data.append(entry)

    def __str__(self) -> str:
        return 'year temperature temperature_smoothed\n' + \
            '\n'.join(str(entry) for entry in self.data)

    def get_year(self) -> List[int]:
        return [entry.year for entry in self.data]

    def get_temperature(self) -> List[float]:
        return [entry.temperature for entry in self.data]

    def get_temperature_smoothed(self) -> List[float]:
        return [entry.temperature_smoothed for entry in self.data]


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title('Simple Weather Data Analysis')
        self.create_widgets()

    def create_widgets(self) -> None:
        self.read_from_file_button = tk.Button(
            self, text='从文件读取', command=self.read_from_file
        )
        self.read_from_file_button.grid(row=0, column=0, pady=5, sticky='E')

        self.status_label = tk.Label(self, text='未加载数据')
        self.status_label.grid(row=0, column=1, pady=5, sticky='W')

        self.plot = FigureCanvasTkAgg(
            Figure(figsize=(13, 8), dpi=120), master=self)
        self.plot.get_tk_widget().grid(
            row=1, column=0, columnspan=2, padx=5, pady=5, sticky='NSEW'
        )

    @staticmethod
    def validate_input(lines: List[str]) -> None:
        if len(lines) < 5:
            raise Exception('数据条数过少')
        for line in lines:
            if len(line.split()) != 3:
                raise Exception('文件格式错误')
        years = [int(line.split()[0]) for line in lines]
        for i in range(len(years) - 1):
            if years[i + 1] - years[i] != 1:
                raise Exception('年份不连续递增')

    def read_from_file(self) -> None:
        file_path = askopenfilename(
            title='选择文件', filetypes=[('文本文件', '*.txt')]
        )
        if not file_path:
            return
        with open(file_path, 'r') as f:
            lines = f.readlines()[1:]
            file_name = file_path.split('/')[-1]

            try:
                self.validate_input(lines)
            except Exception as e:
                self.status_label.config(
                    text='{} 加载失败：{}'.format(file_name, e)
                )
                return

            self.status_label.config(text='已加载 {}'.format(file_name))
            self.create_plot(WeatherData(
                [WeatherDataEntry.try_from(*line.split()) for line in lines]
            ))

    def create_plot(self, data: WeatherData):
        years: List[int] = data.get_year()
        temperatures: List[float] = data.get_temperature()
        std_lowess: np.ndarray = np.array(data.get_temperature_smoothed())
        my_lowess: np.ndarray = lowess(np.array(temperatures), 5)
        diff: np.ndarray = std_lowess - my_lowess

        self.plot.figure.clear()

        ax = self.plot.figure.add_subplot()
        ax.plot(
            years, temperatures, marker=".", markersize=2, linewidth=0.5,
            label='原始数据', color='lightgrey'
        )
        ax.plot(
            years, std_lowess, marker="o", markersize=2, label='样例 Lowess(5)'
        )
        ax.plot(
            years, my_lowess, marker="o", markersize=2,
            label='{} Lowess(5)'.format(
                'statsmodels' if getenv('SM_LOWESS') else '手动实现'
            )
        )
        ax.plot(
            years, diff, marker="o", markersize=1, linestyle='', label='差值'
        )

        width = max(years) - min(years)
        step = 20 if width > 100 else 10 if width > 50 else 5
        ax.set_xticks(range(
            ((min(years) - 1) // step + 1) * step,
            max(years) // step * step + 1,
            step,
        ))
        ax.set_xlabel('年份')
        ax.set_ylabel('温度')
        ax.set_title('年份-温度图')
        ax.grid(True)
        ax.legend()

        self.plot.figure.tight_layout()
        self.plot.draw()


def main() -> None:
    if getenv('SM_LOWESS'):
        sys.stderr.write('Using statsmodels `lowess`\n')
    else:
        sys.stderr.write('Using manually implemented `lowess`\n')

    plt.rcParams['font.sans-serif'] = ['HYZhengYuan']  # 在其他环境中可能需要修改字体
    plt.rcParams['axes.unicode_minus'] = False
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()
