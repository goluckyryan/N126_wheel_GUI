# About

This is a GUI for target wheel control for the N=126 factory at ATLAS, ANL.

# Setup

The required python packages are in **requirements.txt**

```sh
>python3 -m pip install -r requirements.txt
```

# influxDB2

https://docs.influxdata.com/influxdb/v2/install/?t=Linux

# Create Python Virtual Enviroment

make sure you have the required packages
```sh
> sudo apt install python3-venv python3-pip
```

create virtual enviroment
```sh
>cd <path_you_want>
>python3 -m venv <name_of_the_venv>
```

to activiate
```sh
>source <path_you_want>/<name_of_the_vene>/bin/activate
```

to deactiviate
```
>deactivate
```

# possible issues

when install in a fresh system, the Qt6 may complaint
```sh
qt.qpa.plugin: From 6.5.0, xcb-cursor0 or libxcb-cursor0 is needed to load the Qt xcb platform plugin.
qt.qpa.plugin: Could not load the Qt platform plugin "xcb" in "" even though it was found.
```

to solve this
```sh
>sudo apt install libxcb-cursor0
```

# Raw Command List

These are the raw commands sent to the Applied Motion controller via TCP. They can also be sent manually through the "Send CMD" field in the GUI.

## Control Commands

| Command | Description |
|---------|-------------|
| `SK` | Stop/Kill - stops all movement |
| `RE` | Reset controller |
| `CJ` | Start continuous jog (spin) |
| `SJ` | Stop jog (spin) |
| `FL` | Execute move (fetch/load movement) |
| `SHX0H` | Seek home position |
| `QX1` | Start QX1 sweep program |
| `QX4` | Start QX4 position lock program |

## Parameter Commands

| Command | Description | Unit |
|---------|-------------|------|
| `DI{value}` | Set move distance | steps |
| `EP{value}` | Set encoder position | steps |
| `AM{value}` | Set max acceleration | rev/s^2 |
| `AC{value}` | Set acceleration rate | rev/s^2 |
| `DE{value}` | Set deacceleration rate | rev/s^2 |
| `VE{value}` | Set velocity | rev/s |
| `JS{value}` | Set jog speed | rev/s |
| `JA{value}` | Set jog acceleration | rev/s^2 |

## I/O and Register Commands

| Command | Description |
|---------|-------------|
| `IO7` | Set I/O to 7 |
| `RMNO` | Hold motor current |
| `RLO0` | Release motor |
| `RL1{mask}` | Set sweep mask (16-bit spoke enable) |
| `RL2{width}` | Set spoke width (steps) |
| `RL3{offset}` | Set spoke offset (steps) |
| `RL4{speed}` | Set sweep speed (value * 4 = raw, 0.25 rpm/unit) |
| `RL5{cutoff}` | Set sweep cutoff (value * 4 = raw, 0.25 rpm/unit) |
| `RL6{pos}` | QX4: set encoder demand position |
| `RL7{rate}` | QX4: set control update rate (100 us/unit) |
| `RL8{speed}` | QX4: set slew speed (0.25 rpm/unit) |
| `RL9{speed}` | QX4: set servo slew speed (0.25 rpm/unit) |

## Query Commands

| Command | Returns |
|---------|---------|
| `CM` | Command mode |
| `JS` | Jog speed (rev/s) |
| `JA` | Jog acceleration (rev/s^2) |
| `AM` | Max acceleration (rev/s^2) |
| `AC` | Acceleration rate (rev/s^2) |
| `DE` | Deacceleration rate (rev/s^2) |
| `VE` | Velocity (rev/s) |
| `DI` | Move distance (steps) |
| `IO` | I/O status (8-bit) |
| `RUp1` | Firmware program status |
| `RU11` | Sweep mask |
| `RU21` | Spoke width |
| `RU31` | Spoke offset |
| `RU41` | Sweep speed (raw / 4 = rpm) |
| `RU51` | Sweep cutoff (raw / 4 = rpm) |
| `RU61` | QX4 encoder demand position |
| `RU71` | QX4 control update rate |
| `RU81` | QX4 slew speed |
| `RU91` | QX4 servo slew speed |
| `RU;1` | QX4 motor demand position |
| `RUe1` | Encoder position (steps) |
| `RUt1` | Temperature (raw / 10 = C) |
| `RUv1` | Encoder velocity (raw / 4 = rpm) |
| `RUw1` | Motor velocity (raw / 4 = rpm) |
| `RUx1` | Torque reference |