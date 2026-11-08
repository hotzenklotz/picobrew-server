ALLOWED_FILE_EXTENSIONS = [".xml", ".beerxml"]
# Data directories, relative to PICOBREW_DATA_DIR (default: the working directory).
DATA_DIR_ENV = "PICOBREW_DATA_DIR"
RECIPE_PATH = "recipes"
# Legacy JSON session logs and error reports are imported from here into BREW_DATABASE.
SESSION_PATH = "sessions"
BREW_DATABASE = "sessions/brew_sessions.sqlite3"
MACHINE_PATH = "machines"
SYSTEM_USER = "00000000000000000000000000000000"
LOCAL_USER = "dd945a43414a52cb99cfa93b29668f30"
# Built-in cleaning programs ("Cleaning v1", "Rinse v3"); sessions running them are cleaning sessions.
CLEANING_V1_ID = "7f489e3740f848519558c41a036fe2cb"
RINSE_V3_ID = "0160275741134b148eff90acdd5e462f"
CLEANING_RECIPE_IDS = frozenset({CLEANING_V1_ID, RINSE_V3_ID})

# Display names for the four DS18B20 sensors in session logs, in chart order.
# Firmware 1.1.14 sends "2/<wort>|1/<heat1>|3/<board>|4/<heat2>" (brew_logTemperatures);
# HEAT2 is the backup heat sensor. Readings are integer degrees Fahrenheit.
SENSOR_LABELS = {
    2: "Wort",
    1: "Heat 1",
    4: "Heat 2",
    3: "Board",
}
TEMPERATURE_UNIT = "°F"

# Reset reasons reported through /API/sessionerror (see docs/PicoBrew-API.md).
SESSION_ERROR_LABELS = {
    300: "JTAG reset",
    301: "External reset",
    302: "Power-off reset",
    303: "Brownout reset",
    304: "Reset",
    305: "Jump to 0 reset",
}
