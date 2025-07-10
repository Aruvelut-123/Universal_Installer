import json
import os

command = 'pyinstaller -y --clean --onefile'

#command += " --windowed"

with open("metadata.json", "r", encoding="utf-8") as f:
    md = json.load(f)

if "icon" in md:
    command += " -i "+md["icon"]

command += " main.py"
os.system(command)