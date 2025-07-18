# About

This is a GUI for target wheel control for the N=126 factory at ATLAS, ANL.

# Setup

The required python packages are in **requirements.txt**

```sh
>python3 -m pip install -r requirements.txt
```

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