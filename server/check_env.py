import os
from decouple import config

os.environ["VERIFY_SSL"] = "false"
try:
    val = config("VERIFY_SSL", default="true", cast=bool)
    print(f"VERIFY_SSL cast result: {val} (type: {type(val)})")
except Exception as e:
    print(f"VERIFY_SSL cast failed: {e}")

os.environ["SPLUNK_PORT"] = "8089"
try:
    val = int(os.environ.get("SPLUNK_PORT", "8089"))
    print(f"SPLUNK_PORT cast result: {val}")
except Exception as e:
    print(f"SPLUNK_PORT cast failed: {e}")
