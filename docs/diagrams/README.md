# Zigbee field guide illustrations

Original illustrations for the [README field guide](../../README.md#zigbee-field-guide-from-firmware-to-recovery).
Each has an editable, static HTML source with inline SVG and a generated SVG
for GitHub. All use a 960 × 600 viewBox, accessible titles/descriptions, and the
user-selected default light style from
[diagram-design](https://github.com/cathrynlavery/diagram-design/tree/f4547ee95f88e5b28a52517feff6b6c11cc657f9).

- **Four update boundaries:** [SVG](zha-device-boundaries.svg) · [HTML](zha-device-boundaries.html).
  Original SLZB-06 architecture; software, core, radio, and endpoint updates are separate.
- **Remote UART bridge:** [SVG](remote-uart-bridge.svg) · [HTML](remote-uart-bridge.html).
  Conceptual NXP/ESP8266 setup from part 28 and RemoteLogger. Arrows show the
  flashing connection, log flow, serial channel, and control signals; they are
  not a pin-by-pin electrical schematic.
- **UART ownership:** [SVG](uart-ownership.svg) · [HTML](uart-ownership.html).
  Simplified state machine for three UART roles. It omits individual startup
  waits and exceptions; the upstream implementation remains authoritative.

The last two diagrams describe **JN5169**, not the SLZB-06. Their pins, baud rates,
and bootloader must not be applied to ESP32 or CC2652P. Sources and reviewed
revisions are listed in [sources](../sources.md#hello-zigbee-world-field-guide).

## Edit and regenerate

Edit the HTML first. From the root of this repository, with Python 3 and Git:

```sh
diagram_tools="$(mktemp -d)"
git clone https://github.com/cathrynlavery/diagram-design.git "$diagram_tools"
git -C "$diagram_tools" checkout --detach f4547ee95f88e5b28a52517feff6b6c11cc657f9

for source in docs/diagrams/*.html; do
  python3 "$diagram_tools/skills/diagram-design/scripts/export_svg.py" "$source"
done
python3 "$diagram_tools/skills/diagram-design/scripts/self_check.py" docs/diagrams/*.html
python3 "$diagram_tools/scripts/verify-geometry.py" docs/diagrams/*.html
```

Open each HTML file in a browser to inspect the result. Also inspect its SVG
as an HTML `<img>`: GitHub's image context does not load the Google Fonts used
by the standalone HTML. The explicit Arial/Georgia/Courier New fallbacks keep
text readable there; exact letter shapes differ. Both contexts were visually
checked. On narrow screens the HTML scrolls the figure locally; GitHub scales
the SVG, which can be opened separately for full-size reading.

No JavaScript, live household addresses, credentials, or hardware access is
included. The diagrams are original MIT-licensed documentation. Upstream
articles and tools retain their own terms; no upstream article illustrations
or implementation code are copied here.
