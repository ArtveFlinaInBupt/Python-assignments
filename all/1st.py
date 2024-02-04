#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import simpledialog
from typing import List, Optional


class Color:
    class ColorError(Exception):
        def __init__(self, color: str):
            super().__init__(f'"{color}" is not a valid color.')

    DEFAULT = '#ffffff'

    def __init__(self, r: int, g: int, b: int):
        if not (self.valid_u8(r) and self.valid_u8(g) and self.valid_u8(b)):
            raise self.ColorError(f'rgb({r}, {g}, {b})')
        self.r = r
        self.g = g
        self.b = b

    @classmethod
    def from_hex(cls, hex_str: str) -> 'Color':
        try:
            if hex_str.startswith('#'):
                hex_str = hex_str[1:]
            r: int = int(hex_str[:2], 16)
            g: int = int(hex_str[2:4], 16)
            b: int = int(hex_str[4:], 16)
        except ValueError:
            raise cls.ColorError(f'#{hex_str}')

        return cls(r, g, b)

    @staticmethod
    def default() -> 'Color':
        return Color.from_hex(Color.DEFAULT)

    @staticmethod
    def valid_u8(value: int) -> bool:
        return 0 <= value <= 255

    def __str__(self) -> str:
        return f'#{self.r:02x}{self.g:02x}{self.b:02x}'

    def __repr__(self) -> str:
        return f'Color({self.r}, {self.g}, {self.b})'


class Point:
    def __init__(self, x: float, y: float):
        self.x: float = x
        self.y: float = y

    def __repr__(self) -> str:
        return f'Point({self.x}, {self.y})'


class Shape:
    def __init__(self, canvas: Optional[tk.Canvas]):
        self.canvas: Optional[tk.Canvas] = canvas
        self.color: Optional[Color] = None

    def draw(self) -> None:
        raise NotImplementedError(
            'The `draw` method must be implemented by subclasses.')


class Rectangle(Shape):
    def __init__(self, canvas: Optional[tk.Canvas], p1: Point, p2: Point, color: Optional[Color] = None):
        super().__init__(canvas)
        self.p1: Point = p1
        self.p2: Point = p2
        self.color: Optional[Color] = color

    def draw(self) -> None:
        if self.canvas is None:
            raise ValueError('The `canvas` property must be set.')

        self.canvas.create_rectangle(
            self.p1.x, self.p1.y, self.p2.x, self.p2.y, fill=str(self.color if self.color else Color.default()))


class Circle(Shape):
    def __init__(self, canvas: Optional[tk.Canvas], center: Point, radius: float, color: Optional[Color] = None):
        super().__init__(canvas)
        self.center: Point = center
        self.radius: float = radius
        self.color: Optional[Color] = color

    @classmethod
    def with_two_points(cls, canvas: Optional[tk.Canvas], center: Point, side: Point, color: Optional[Color] = None) -> 'Circle':
        radius: float = ((center.x - side.x)**2 + (center.y - side.y)**2)**0.5
        return cls(canvas, center, radius, color)

    def draw(self) -> None:
        if self.canvas is None:
            raise ValueError('The `canvas` property must be set.')

        x0: float = self.center.x - self.radius
        y0: float = self.center.y - self.radius
        x1: float = self.center.x + self.radius
        y1: float = self.center.y + self.radius
        self.canvas.create_oval(
            x0, y0, x1, y1, fill=str(self.color if self.color else Color.default()))


class NewShapeDialog(simpledialog.Dialog):
    def body(self, master: tk.Tk) -> tk.Entry:
        self.result: Optional[Shape] = None
        tk.Label(master, text="Shape (circle/rectangle):").grid(row=0, sticky=tk.W)
        tk.Label(master, text="Color (#rrggbb):").grid(row=1, sticky=tk.W)
        tk.Label(master, text="Point 1 (x, y):").grid(row=2, sticky=tk.W)
        tk.Label(master, text="Point 2 (x, y):").grid(row=3, sticky=tk.W)

        self.shape_entry: tk.Entry = tk.Entry(master)
        self.color_entry: tk.Entry = tk.Entry(master)
        self.point1_entry: tk.Entry = tk.Entry(master)
        self.point2_entry: tk.Entry = tk.Entry(master)

        self.shape_entry.grid(row=0, column=1)
        self.color_entry.grid(row=1, column=1)
        self.point1_entry.grid(row=2, column=1)
        self.point2_entry.grid(row=3, column=1)

        return self.shape_entry

    def apply(self) -> None:
        shape = self.shape_entry.get()
        color_hex = self.color_entry.get()
        point1_str = self.point1_entry.get()
        point2_str = self.point2_entry.get()

        try:
            point1 = Point(*map(float, map(str.strip, point1_str.split(','))))
            point2 = Point(*map(float, map(str.strip, point2_str.split(','))))
            color = Color.from_hex(color_hex)
            if 'circle'.find(shape) == 0:
                self.result = Circle.with_two_points(
                    None, point1, point2, color)
            elif 'rectangle'.find(shape) == 0:
                self.result = Rectangle(
                    None, point1, point2, color)
            else:
                raise ValueError(f"Invalid shape: {shape}")
        except Exception as e:
            print(f"An error occurred: {e}")
            self.result = None


class Display:
    def __init__(self, root: tk.Tk):
        self.root: tk.Tk = root
        self.canvas: tk.Canvas = tk.Canvas(self.root, width=600, height=600)
        self.canvas.pack()
        self.shapes: List[Shape] = []

        self.add_controls()

    def add_shape(self, shape: Shape) -> None:
        self.shapes.append(shape)
        shape.draw()

    def clear_all_shapes(self) -> None:
        self.shapes.clear()
        self.canvas.delete("all")

    def prompt_for_shape(self) -> None:
        dialog: NewShapeDialog = NewShapeDialog(self.root)
        shape: Optional[Shape] = dialog.result

        if shape:
            shape.canvas = self.canvas
            self.add_shape(shape)

    def add_controls(self) -> None:
        button_frame: tk.Frame = tk.Frame(self.root)
        button_frame.pack(fill=tk.X)

        clear_button: tk.Button = tk.Button(
            button_frame, text="Clear All", command=self.clear_all_shapes)
        clear_button.pack(side=tk.RIGHT)

        add_shape_button: tk.Button = tk.Button(
            button_frame, text="Add Shape", command=self.prompt_for_shape)
        add_shape_button.pack(side=tk.RIGHT)


def main() -> None:
    root: tk.Tk = tk.Tk()
    root.title('Shapes Display')

    display: Display = Display(root)

    rect: Shape = Rectangle(display.canvas, Point(150, 150),
                            Point(250, 200), Color.from_hex('#8866ff'))
    circ: Shape = Circle(display.canvas, Point(300, 300),
                         50, Color.from_hex('#ff6688'))
    display.add_shape(rect)
    display.add_shape(circ)

    root.mainloop()


if __name__ == "__main__":
    main()
