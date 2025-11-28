import re
from datetime import datetime

log_pattern = re.compile(
    r"(?P<month>\w{3}) (?P<day>\d{2}) (?P<time>\d{2}:\d{2}:\d{2}) (?P<rest>.*)"
)

year = 2025

with (
    open("data/ace_syslog_400.log", "r") as f_in,
    open("data/ace_syslog_400.jsonl", "w") as f_out,
):
    for line in f_in:
        line = line.strip()
        m = log_pattern.match(line)

        if m:
            month, day, time, rest = m.groups()
            ts = datetime.strptime(f"{month} {day} {time}", "%b %d %H:%M:%S").replace(
                year=year
            )
            severity = None

            # severity is the last char before ':'
            code_match = re.search(r"(ACE\d+)([WEI]):", rest)
            if code_match:
                msg_code, sev = code_match.groups()
                severity = sev
            else:
                severity = "U"

            # write JSONL
            entry = {
                "text": line,
                "timestamp": ts.isoformat(sep=" "),
                "severity": severity,
            }
            import json

            f_out.write(json.dumps(entry) + "\n")
        else:
            entry = {
                "text": line,
                "timestamp": None,
                "severity": "U",
            }
            import json

            f_out.write(json.dumps(entry) + "\n")

print("File converted to system.jsonl!")
