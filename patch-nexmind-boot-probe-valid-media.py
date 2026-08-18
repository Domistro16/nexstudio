#!/usr/bin/env python3
from pathlib import Path
import re

path = Path("scripts/nexmind-runtime-boot-probe.py")
if not path.exists():
    raise SystemExit("Run this from the NexStudio root; scripts/nexmind-runtime-boot-probe.py was not found.")

text = path.read_text(encoding="utf-8")

replacement = "PNG='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAbUlEQVR42u3XMQ0AIAxFQeQgAmGoQwkikICBMnWBcAljB256+WWNFr7aZ/huuy8AAAAAACnAKx893QMAAAAA5ABKDAAAAGAPKDEAAACAPaDEAAAAAPaAEgMAAADYA0oMAAAAYA8oMQAAAMA3gA2g9DGWVZTODQAAAABJRU5ErkJggg=='"
new_text, count = re.subn(r"^PNG=.*$", replacement, text, count=1, flags=re.M)
if count != 1:
    raise SystemExit("Could not find the PNG probe fixture line.")

# Preserve provider error bodies so a future 4xx is diagnosable.
old = "    except Exception as e:return False,str(e)[:300]"
new = """    except urllib.error.HTTPError as e:
        body=e.read().decode('utf-8',errors='replace')[:700]
        return False,f'HTTP {e.code}: {body}'
    except Exception as e:return False,str(e)[:300]"""
if old in new_text:
    new_text = new_text.replace(old, new, 1)

path.write_text(new_text, encoding="utf-8", newline="\n")
print("Patched boot probe with a valid 64x64 embedded PNG and detailed HTTP errors.")
