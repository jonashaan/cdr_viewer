from datetime import timedelta
import warnings
from csv import Sniffer
from typing import Any, Tuple, List, Optional

import pandas as pd
from chardet import UniversalDetector
from kivy.metrics import dp
from numpy import recarray
from pandas import DataFrame
import pytz
from pandas._libs.tslibs.timestamps import Timestamp

warnings.filterwarnings("ignore")

LOCAL_TIMEZONE = pytz.timezone('Europe/Berlin')


class ShowErrorPopup:
    def __init__(self, title: str, message: str):
        self.title = title
        self.message = message


def convert_empty_category(val: str) -> str | Any:
    if len(val) < 2 or "\\" in val or val is None:
        return ""
    elif "E+" in val:
        # Replace comma with period and convert to float
        if "," in val:
            val = float(val.replace(",", "."))
        return "+" + str(int(val))
    else:
        return val


def convert_empty_time(val: str) -> str | Any:
    if pd.isna(val):
        return ""
    try:
        # If it's a Unix timestamp, convert to datetime
        timestamp = pd.to_datetime(val, unit="s")
    except ValueError:
        # If it's a datetime string, parse it directly
        timestamp = pd.to_datetime(val)
    return timestamp


def convert_to_table(dataframe: pd.DataFrame, full: bool = False) -> tuple[list[tuple[str, float]], recarray]:
    # standard: callingPartyNumber, originalCalledPartyNumber, dateTimeConnect, origDeviceName, duration
    if full:
        return list(dataframe.columns), dataframe.to_records(index=False)
    else:
        df = dataframe[["dateTimeOrigination",
                        "callingPartyNumber",
                        "originalCalledPartyNumber",
                        "dateTimeConnect",
                        "duration",
                        "origDeviceName"]]
        col_text_size = 20
        colnames = [
            (f"[size={col_text_size}]Zeitstempel[/size]", dp(35)),
            (f"[size={col_text_size}]Anrufer[/size]", dp(35)),
            (f"[size={col_text_size}]Gewählte Nummer[/size]", dp(39)),
            (f"[size={col_text_size}]Verbunden um[/size]", dp(32)),
            (f"[size={col_text_size}]Dauer[/size]", dp(25)),
            (f"[size={col_text_size}]Gerät[/size]", dp(49))
        ]
        return colnames, df.to_records(index=False)


from datetime import timedelta


def check_date_time_connect(val: str) -> bool:
    if pd.isna(val):
        return True
    # check if val is a string formatted timestamp with unix time 0
    if isinstance(val, Timestamp) and val.year == 1970:
        return True


def process_chunks(reader: Any, callback: Any, chunk_size: int) -> pd.DataFrame:
    df = pd.DataFrame()
    for i, chunk in enumerate(reader):
        chunk = chunk.dropna(subset=["dateTimeOrigination"])
        chunk["dateTimeConnect"] = chunk.apply(
            lambda x: x["dateTimeDisconnect"] if check_date_time_connect(x["dateTimeConnect"]) else x["dateTimeConnect"], axis=1)
        chunk["duration"] = chunk["dateTimeDisconnect"] - chunk["dateTimeOrigination"]
        chunk["duration"] = chunk["duration"].apply(
            lambda x: "" if pd.isna(x) else f"{x.seconds // 3600:02d}:{x.seconds % 3600 // 60:02d}:{x.seconds % 60:02d}"
        )

        # Convert Unix timestamps to datetime objects
        chunk["dateTimeOrigination"] = chunk["dateTimeOrigination"].apply(lambda x: pd.to_datetime(x, unit='s'))
        chunk["dateTimeConnect"] = chunk["dateTimeConnect"].apply(lambda x: pd.to_datetime(x, unit='s'))
        chunk["dateTimeDisconnect"] = chunk["dateTimeDisconnect"].apply(lambda x: pd.to_datetime(x, unit='s'))

        # Manually add time difference for Berlin time (1 hour during standard time, 2 hours during daylight saving time)
        def adjust_to_berlin_time(dt):
            if dt.year <= 2021:
                dst_start = pd.to_datetime(f"{dt.year}-03-28 01:00:00")
                dst_end = pd.to_datetime(f"{dt.year}-10-31 01:00:00")
            else:
                dst_start = pd.to_datetime(f"{dt.year}-03-27 01:00:00")
                dst_end = pd.to_datetime(f"{dt.year}-10-30 01:00:00")

            if dst_start <= dt < dst_end:
                return dt + timedelta(hours=2)  # Add 2 hours for daylight saving time
            else:
                return dt + timedelta(hours=1)  # Add 1 hour for standard time

        chunk["dateTimeOrigination"] = chunk["dateTimeOrigination"].apply(adjust_to_berlin_time)
        chunk["dateTimeConnect"] = chunk["dateTimeConnect"].apply(adjust_to_berlin_time)
        chunk["dateTimeDisconnect"] = chunk["dateTimeDisconnect"].apply(adjust_to_berlin_time)

        # Convert datetime objects to strings
        chunk["dateTimeOrigination"] = chunk["dateTimeOrigination"].apply(lambda x: x.strftime("%d.%m.%y %H:%M:%S"))
        chunk["dateTimeConnect"] = chunk["dateTimeConnect"].apply(lambda x: x.strftime("%H:%M:%S"))
        chunk["dateTimeDisconnect"] = chunk["dateTimeDisconnect"].apply(lambda x: x.strftime("%d.%m.%y %H:%M:%S"))

        df = df.append(chunk)
        callback(f"{(i + 1) * chunk_size} Chunks geladen...")
    return df



def load_data(csv_file: str, callback: Any, as_dataframe: bool = False, full: bool = False) -> Tuple[Optional[DataFrame], Optional[str]]:
    req_cols = {
        "dateTimeOrigination"               : "uint32",
        "callingPartyNumber"                : "str",
        "callingPartyUnicodeLoginUserID"    : "str",
        "originalCalledPartyNumber"         : "str",
        "finalCalledPartyUnicodeLoginUserID": "str",
        "dateTimeConnect"                   : "uint32",
        "dateTimeDisconnect"                : "uint32",
        "origDeviceName"                    : "str",
    }
    converters = {
        "callingPartyUnicodeLoginUserID"    : convert_empty_category,
        "finalCalledPartyUnicodeLoginUserID": convert_empty_category,
        "origDeviceName"                    : convert_empty_category,
        "callingPartyNumber"                : convert_empty_category,
        "originalCalledPartyNumber"         : convert_empty_category,
        "dateTimeOrigination"               : convert_empty_time,
        "dateTimeConnect"                   : convert_empty_time,
        "dateTimeDisconnect"                : convert_empty_time,
    }

    with open(csv_file, "r") as f:
        dialect = Sniffer().sniff(f.read(2048))
    df = pd.DataFrame()
    chunk_size = 16
    error_message = None
    try:
        df = process_chunks(
            reader=pd.read_csv(  # type: ignore
                csv_file, chunksize=chunk_size, usecols=[*req_cols], dtype=req_cols, converters=converters,
                delimiter=dialect.delimiter
            ), callback=callback, chunk_size=chunk_size
        )
    except UnicodeDecodeError:
        callback("Scanne Encoding...")
        detector = UniversalDetector()
        with open(csv_file, "rb") as f:
            for line in f:
                detector.feed(line)
                if detector.done:
                    break
        detector.close()
        result = detector.result
        callback(f"Versuche mit '{result['encoding']}'...")
        try:
            df = process_chunks(
                reader=pd.read_csv(  # type: ignore
                    csv_file, chunksize=chunk_size, usecols=[*req_cols], dtype=req_cols, converters=converters,
                    delimiter=dialect.delimiter, encoding=result["encoding"]
                ), callback=callback, chunk_size=chunk_size
            )
        except Exception as e:
            error_message = ShowErrorPopup("Fehler", f"Datei kann nicht geladen werden: {str(e)}")
    except Exception as e:
        error_message = ShowErrorPopup("Fehler", f"Datei kann nicht geladen werden: {str(e)}")
    if as_dataframe:
        return df, error_message
    else:
        return convert_to_table(df, full)
#
# if __name__ == '__main__':
#     data = load_data("Test_uc_log.csv", callback=lambda x: x, as_dataframe=True)
#     data.info(verbose=False, memory_usage="deep")
#     print(data.to_string())
#     print("ende")
