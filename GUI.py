import re
import threading
import tkinter as tk
from tkinter import filedialog
from typing import Any

import pandas as pd
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.config import Config
from kivy.core.window import Window
from kivy.core.window._window_sdl2 import _WindowSDL2Storage
from kivy.core.window.window_sdl2 import WindowSDL
from kivy.metrics import dp
from kivy.properties import ObjectProperty
from kivy.uix.popup import Popup
from kivymd.app import MDApp
from kivymd.uix.behaviors import HoverBehavior
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.datatables import MDDataTable
from kivymd.uix.label import MDLabel
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.spinner import MDSpinner
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDTopAppBar


from parser import convert_to_table, ShowErrorPopup
from parser import load_data as parse
from export import create_pdf as export

Config.set('input', 'mouse', 'mouse,disable_multitouch')



# in der .spec file: from kivy_deps import sdl2, glew

# nord palette
custom_colors = {
    "Teal"    : {
        "500": "#8FBCBB",
    },
    "Blue"    : {
        "500": "#88C0D0",
    },
    "BlueGray": {
        "500": "#81A1C1",
    },
    "Indigo"  : {
        "500": "#5E81AC",
    },
    "Red"     : {
        "500": "#BF616A",
    },
    "Orange"  : {
        "500": "#D08770",
    },
    "Yellow"  : {
        "500": "#EBCB8B",
    },
    "Green"   : {
        "500": "#A3BE8C",
    },
    "Purple"  : {
        "500": "#B48EAD",
    },
    "Dark"    : {
        "StatusBar"     : "3B4252",
        "AppBar"        : "#3B4252",
        "Background"    : "#3B4252",
        "CardsDialogs"  : "#3B4252",
        "FlatButtonDown": "#4C566A",
    },
}


# lmao. label in texinput geändert für die datatable cells
# TextInput:
#                 id: label
#                 text: " " + root.text
#                 readonly: True
#                 foreground_color:
#                     (0.92549019607, 0.93725490196, 0.95686274509, 1)
#                 background_color:
#                     (0.23137254902, 0.25882352941, 0.32156862745, 1)
#                 cursor_blink: False
#                 cursor_color:
#                     (1, 1, 1, 0)
#                 font_size: "18 sp"
#                 hint_text_color:
#                     (0, 0, 0, 0)
#                 background_normal: ""
#                 padding: "0dp", "0dp", "0dp", "0dp"
#                 padding_y: self.height/2 - self.line_height/2

def mouseEnter(instance):
    Window.raise_window()
Window.bind(on_cursor_enter=mouseEnter)


# weil kivy schmutz ist
class HoverTextInput(HoverBehavior, MDTextField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # fixes 'HoverTextInput' object has no attribute '_win'
        self._win = _WindowSDL2Storage()

    def on_enter(self, *args):
        WindowSDL.set_system_cursor(self, cursor_name='ibeam')

    def on_leave(self, *args):
        WindowSDL.set_system_cursor(self, cursor_name='arrow')


class ModifiedPopup(Popup):
    def __init__(self, allow_manual_dismiss=True, **kwargs):
        super().__init__(**kwargs)
        self.allow_manual_dismiss = allow_manual_dismiss

    def on_touch_down(self, touch):
        if self.allow_manual_dismiss:
            return super().on_touch_down(touch)
        else:
            return False



class Table(MDApp):
    spinner_widget = ObjectProperty()

    def build(self):
        # theming
        for custom_color_name, custom_color_hues in custom_colors.items():
            for hue, value in custom_color_hues.items():
                self.theme_cls.colors[custom_color_name].update({hue: value})
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Indigo"

        # widgets
        self.popup = None
        self.df = pd.DataFrame()
        self.spinner_widget = MDSpinner(
            size_hint=(None, None),
            size=(dp(46), dp(46)),
            pos_hint={'center_x': .5, 'center_y': .5},
            active=True,
            palette=[[0.28627450980392155, 0.8431372549019608, 0.596078431372549, 1],
                     [0.3568627450980392, 0.3215686274509804, 0.8666666666666667, 1],
                     [0.8862745098039215, 0.36470588235294116, 0.592156862745098, 1],
                     [0.8784313725490196, 0.9058823529411765, 0.40784313725490196, 1],
                     ]
        )
        self.popup_label = MDLabel(
            text="...",
            text_size=(None, None),
            halign="center",
        )
        self.search_bar = HoverTextInput(
            hint_text="Suche",
            size_hint_x=2.25,
            pos_hint={"y": 0.6},
            icon_right='magnify',
            detect_visible=False,
        )
        self.toolbar = MDTopAppBar(
            title="Anrufe",
            right_action_items=[["text-box-plus-outline", self.load_table, "CSV Datei"],
                                ["help-circle-outline", self.show_help, "Hilfe"],
                                ["file-pdf-box", self.export_as_pdf, "Exportieren"]],
            md_bg_color="#2E3440"
        )
        self.toolbar.children[0].size_hint = (0.4, None)
        self.toolbar.children[0].add_widget(self.search_bar)
        self.search_bar.bind(text=self.search_bar_callback)

        # layouts
        self.popup_layout = MDBoxLayout(orientation='vertical')
        self.boxlayout = MDBoxLayout(
            orientation='vertical',
        )
        self.boxlayout.add_widget(self.toolbar)

        self.scroll_view = MDScrollView(
            scroll_type=['bars'],
            bar_width=dp(10),
            scroll_distance=dp(30),
        )
        self.boxlayout.add_widget(self.scroll_view)

        Window.size = (dp(1130), Window.size[1])
        return self.boxlayout

    def show_help(self, *args, **kwargs):
        self.popup_layout.add_widget(
            MDLabel(
                markup=True,
                text="""[ref=top][size=24]Allgemein[/size][/ref]

- Über den Button oben rechts lassen sich die Telefoniedaten CSV-Dateien einlesen.
- Auftretende (Fehler-)Meldungen können mit einem Mausklick an beliebiger Stelle geschlossen werden

[ref=top][size=24]Suchfunktion[/size][/ref]

- Ohne Beschränkung: Es werden alle Zeilen angezeigt, welche den Suchbegriff irgendwo enthalten
    - Beispiel:
        - 90123 -> Alle Zeilen, die irgendwo diese Zeichenfolge beinhaltet

- Mit Beschränkung auf Spalten: Es werden alle Zeilen angezeigt, welche den Suchbegriff irgendwo in der entsprechenden Spalte enthalten
    - Beispiel:
        - "Spaltenname":"Suchbegriff"
        - Anrufer:90123 -> Alle Zeilen, welche bei "Anrufer" irgendwo "90123" enthalten
"""
            )
        )
        self.popup = ModifiedPopup(
            title='Hilfe',
            content=self.popup_layout,
            size_hint=(.7, .7),
            pos_hint={'center_x': .5, 'center_y': .5},
            separator_height=0,
            background_color=(1, 1, 1, 0),
            allow_manual_dismiss=True
        )
        self.popup.bind(on_dismiss=self.close_popup)
        Animation(opacity=0.5, d=0.5).start(self.boxlayout)
        self.popup.open()

    def export_as_pdf(self, *args, **kwargs):
        root = tk.Tk()
        root.withdraw()
        file = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )
        if file:
            if self.data_tables.column_data:
                export([self.data_tables.column_data, self.data_tables.row_data], file)
                pop_text = "PDF gespeichert unter:\n" + file
            else:
                pop_text = "Keine Daten geladen"

            self.popup_layout.add_widget(
                MDLabel(
                    markup=True,
                    text=pop_text
                )
            )
            self.popup = ModifiedPopup(
                title='Info',
                content=self.popup_layout,
                size_hint=(.7, .7),
                pos_hint={'center_x': .5, 'center_y': .5},
                separator_height=0,
                background_color=(1, 1, 1, 0),
                allow_manual_dismiss=True
            )
            self.popup.bind(on_dismiss=self.close_popup)
            Animation(opacity=0.5, d=0.5).start(self.boxlayout)
            self.popup.open()

    def create_table_widget(self, column_data, row_data):
        self.data_tables = MDDataTable(
            use_pagination=True,
            column_data=column_data,
            row_data=row_data,
            rows_num=50,
            # background_color_cell = "#4C566A",
            background_color_selected_cell="#434C5E",
            background_color_header="#4C566A",
            # background_color="#4C566A",
        )
        # self.data_tables.bind(on_check_press=self.on_row_press)
        self.scroll_view.clear_widgets()
        self.scroll_view.add_widget(self.data_tables)

    def search_bar_callback(self, instance, *args):
        # Cancel any previous scheduled events
        if hasattr(self, '_search_event'):
            Clock.unschedule(self._search_event)

        # Schedule a new event to happen in 3 seconds
        self._search_event = Clock.schedule_once(
            lambda dt: self.filter_data(instance),
            0.5
        )

    def filter_data(self, instance: Any, *args):
        # extra check wegen der verzögerung um 0.5 sekunden
        if self.search_bar.text == instance.text:
            filter_text = re.escape(instance.text)
            if not filter_text.isspace():
                if not self.df.empty:
                    # Define a mapping between the visible column names and their corresponding DataFrame column names
                    column_name_mapping = {
                        "Zeitstempel"    : "dateTimeOrigination",
                        "Anrufer"        : "callingPartyNumber",
                        "Gewählte Nummer": "originalCalledPartyNumber",
                        "Verbunden um"   : "dateTimeConnect",
                        "Dauer"          : "duration",
                        "Gerät"          : "origDeviceName"
                    }

                    # Check if the search term contains a colon und keine uhrzeit
                    if ":" in filter_text and not filter_text[0].isnumeric():
                        # Split the search term by the colon
                        column_tag, search_term = filter_text.split(":", 1)

                        # Get the DataFrame column name corresponding to the column tag
                        df_column = column_name_mapping.get(column_tag)

                        # If the column tag is valid, filter the DataFrame by the specified column
                        if df_column:
                            filtered_df = self.df[self.df[df_column].str.contains(search_term, case=False)]
                        else:
                            # If the column tag is not valid, show an error message and return
                            self.show_popup(msg=ShowErrorPopup("Fehler", "Ungültiger Spaltenname"))
                            return
                    else:
                        # If the search term doesn't contain a colon, search all columns like before
                        filtered_df = self.df[
                            self.df['dateTimeOrigination'].str.contains(filter_text, case=False) |
                            self.df['callingPartyNumber'].str.contains(filter_text, case=False) |
                            self.df['originalCalledPartyNumber'].str.contains(filter_text, case=False) |
                            self.df['dateTimeConnect'].str.contains(filter_text, case=False) |
                            self.df['duration'].str.contains(filter_text, case=False) |
                            self.df['origDeviceName'].str.contains(filter_text, case=False)
                            ]

                    column_data, row_data = convert_to_table(filtered_df)
                    Clock.schedule_once(lambda dt: self.update_ui(column_data, row_data, None), 0)

    def load_table(self, *args, **kwargs):
        root = tk.Tk()
        root.withdraw()
        file = filedialog.askopenfilename()
        if file:
            if not file.endswith('.csv'):
                # Cancel any previously scheduled layout events
                Clock.unschedule(self.popup_layout.do_layout)
                self.show_popup(msg=ShowErrorPopup("Fehler", "Datei ist keine CSV-Datei"))
            else:
                self.scroll_view.clear_widgets()
                self.show_popup(loading=True)
                threading.Thread(target=self.load_data, args=(file,)).start()

    def load_data(self, file):
        def update_popup_text(text):
            self.popup_label.text = text

        self.df, error_message = parse(csv_file=file, callback=update_popup_text, as_dataframe=True)
        if error_message:
            Clock.schedule_once((lambda dt: self.update_ui(None, None, error_message)), 0)
        else:
            column_data, row_data = convert_to_table(self.df)
            Clock.schedule_once(lambda dt: self.update_ui(column_data, row_data, None), 0)
# TODO: fix bug after not csv file und dann csv laden
# TODO: windowed copile
    def update_ui(self, column_data, row_data, error_message):
        if self.popup:
            self.popup.dismiss()
            self.popup_layout.clear_widgets()
        if error_message:
            self.show_popup(msg=error_message)
        else:
            self.create_table_widget(column_data, row_data)

    def show_popup(self, msg: str | ShowErrorPopup = "", loading: bool = False):
        # self.popup_layout = MDBoxLayout(orientation='vertical')

        if not loading:
            self.popup_label.text = msg.title + "\n\n" + msg.message if isinstance(msg, ShowErrorPopup) else msg
            self.popup_layout.add_widget(self.popup_label)
        else:
            self.popup_layout.add_widget(self.spinner_widget)
            self.popup_layout.add_widget(self.popup_label)
            self.spinner_widget.active = True

        self.popup = ModifiedPopup(
            title='',
            content=self.popup_layout,
            size_hint=(.2, .3),
            pos_hint={'center_x': .5, 'center_y': .5},
            separator_height=0,
            background_color=(1, 1, 1, 0),
            allow_manual_dismiss=not loading
        )
        self.popup.bind(on_dismiss=self.close_popup)
        Animation(opacity=0.5, d=0.5).start(self.boxlayout)
        self.popup.open()

    def close_popup(self, *args):
        self.spinner_widget.active = False

        if self.spinner_widget.parent:
            self.spinner_widget.parent.remove_widget(self.spinner_widget)
        if self.popup_label.parent:
            self.popup_label.parent.remove_widget(self.popup_label)
        if self.popup_layout.parent:
            self.popup_layout.parent.remove_widget(self.popup_layout)

        self.popup_layout.clear_widgets()
        if self.popup:
            self.popup.clear_widgets()

        anim = Animation(opacity=1, d=0.5)
        anim.bind(on_complete=lambda *args: Clock.schedule_once(self._set_popup_to_none, 0))
        anim.start(self.boxlayout)

        # Clear any remaining scheduled events
        Clock.unschedule(self.popup_layout.do_layout)

    def _set_popup_to_none(self, dt):
        self.popup = None


if __name__ == '__main__':
    DEBUG = False # wenn für console compilation
    if DEBUG:
        try:
            Table().run()
        except Exception as e:
            print("An error occurred:", e)
        finally:
            input("\nPress Enter to exit...")
    else:
        Table().run()
# TODO: Hilfemenü Copy Paste erklären
# TODO: Wildcardsuche
# Bsp: Uhrzeit:10:**:**  -> String fängt mit 10: an, 2 beliebige Zeichen, :, 2 beliebige Zeichen -> Alles zwischen 10:00:00 und 10:59:59
