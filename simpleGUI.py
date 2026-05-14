#!/usr/bin/env python3

import sys
import os
import json
import math
from collections import deque
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QGridLayout, QHBoxLayout,
    QGroupBox, QLabel, QCheckBox, QLineEdit, QDoubleSpinBox,
    QInputDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent
import time

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from Library import Controller, STEP_PER_REVOLUTION

########################################################################################################

NTARGET = 16
DEFAULT_POS_UPDATE_INTERVAL = 1000  # milliseconds

class TargetButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.isChangeNameMode = False
        self.name = text

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton :
            self.isChangeNameMode = True
            new_title, ok = QInputDialog.getText(
                self,
                "Change Target Name",
                "Enter new name for the target:",
                text=self.text()
            )
            if ok and new_title.strip():
                self.setText(new_title.strip())
                self.name = new_title.strip()
        else:
            self.isChangeNameMode = False

        super().mousePressEvent(event)


class RDoubleSpinBox(QDoubleSpinBox):
    returnPressed = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.valueChanged.connect(self.on_value_changed)
        self.lineEdit().returnPressed.connect(self.on_return_Pressed)

    def on_value_changed(self, value):
        self.setStyleSheet("color: blue;")

    def setValue(self, value: float) -> None:
        self.blockSignals(True)
        super().setValue(value)
        self.setStyleSheet("color: black;")
        self.blockSignals(False)

    def on_return_Pressed(self):
        self.returnPressed.emit()
        self.setStyleSheet("color: black;")


#########################################################################################################
class TargetWheelControlSimple(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Target Wheel Control (Simple)")
        self.target_buttons = []
        self.target_chkBox = []
        self.target_pos = []
        self.target_rev = []
        self.target_names = [f"Target {i}" for i in range(16)]

        self.button_clicked_id = None

        self.controller = Controller()

        self.init_ui()

        self.Load_program_setting()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.Update_Position)
        self.updateTimeInterval = DEFAULT_POS_UPDATE_INTERVAL

        self.Connect_Server()

        self.timer.start(self.updateTimeInterval)
        self.pauseUpdate = False
        self.askPosFromEncoder = True

        self.isQX4Locking = False
        self.isAllSweepEnabled = False

        self.state = 0 # 0: idle, 2: sweep, 3: set target pos, 4: seek home

        self.history_time = deque(maxlen=12000)
        self.history_torque = deque(maxlen=12000)
        self.history_motor_vel = deque(maxlen=12000)
        self.history_enc_vel = deque(maxlen=12000)
        self.history_temp = deque(maxlen=12000)
        self.selectedTimeWindow = 60  # seconds

    def closeEvent(self, event: QCloseEvent):
        self.Save_program_settings()
        self.controller.send_message("SK")
        self.controller.send_message('IO7')
        self.controller.send_message('RLO0')
        self.controller.disconnect()
        event.accept()
        print("============= Program Ended.")

    ######################################################################################## GUI
    def init_ui(self):
        main_layout = QGridLayout()
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        ########### Target group
        target_group = QGroupBox("Target")
        target_layout = QGridLayout()
        target_group.setLayout(target_layout)
        target_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Target Grid Header
        row = 0
        target_layout.addWidget(QLabel("Name"), row, 1, 1, 4)
        target_layout.addWidget(QLabel("Position"), row, 5,1, 2)
        target_layout.addWidget(QLabel("Revolution"), row, 7,1, 2)
        target_layout.addWidget(QLabel("En."), row, 9)

        # Target Buttons Grid
        for i in range(NTARGET):
            row += 1
            target_layout.addWidget(QLabel(str(i)), row, 0)

            btn = TargetButton(self.target_names[i])
            btn.clicked.connect(lambda _, idx=i: self.Target_picked(idx))
            self.target_buttons.append(btn)
            target_layout.addWidget(btn, row, 1, 1, 4)

            le = QLineEdit(str(int(STEP_PER_REVOLUTION/NTARGET)*i))
            le.returnPressed.connect(lambda idx=i: self.SetPosition(idx))
            self.target_pos.append(le)
            le.setReadOnly(True)
            target_layout.addWidget(le, row, 5, 1, 2)

            le2 = QLineEdit(str(int(STEP_PER_REVOLUTION/NTARGET)*i/STEP_PER_REVOLUTION))
            le2.setReadOnly(True)
            self.target_rev.append(le2)
            target_layout.addWidget(le2, row, 7, 1, 1)

            chkBox = QCheckBox()
            chkBox.clicked.connect(lambda _, idx=i: self.Sweep_picked(idx))
            self.target_chkBox.append(chkBox)
            target_layout.addWidget(chkBox, row, 9)

        # Message display
        row += 1
        self.message = QLineEdit()
        self.message.setReadOnly(True)
        self.message.setEnabled(False)
        self.message.setText("message display")
        target_layout.addWidget(self.message, row, 1, 1, 6)

        self.chkAll = QPushButton("Enable All Sweep")
        target_layout.addWidget(self.chkAll, row, 7, 1, 3)
        self.chkAll.clicked.connect(self.setAllSweepTargets)

        # Set Position / Lock
        row += 1
        target_layout.addWidget(QLabel("Set Position : "), row, 1, 1, 3)
        self.qx4SetPos = QLineEdit("0")
        self.qx4SetPos.setFixedWidth(60)
        self.qx4SetPos.returnPressed.connect(self.SetQX4Position)
        target_layout.addWidget(self.qx4SetPos, row, 4, 1, 1)

        self.bnLockPos = QPushButton("Lock Position")
        target_layout.addWidget(self.bnLockPos, row, 5, 1, 5)
        self.bnLockPos.clicked.connect(self.LockPosition)

        #&########## Servers
        server_group = QGroupBox("Servers")
        server_layout = QGridLayout()
        server_group.setLayout(server_layout)

        self.leIP = QLineEdit()
        self.lePort = QLineEdit()
        self.bnConnect = QPushButton("Connect")
        self.bnConnect.clicked.connect(self.Connect_Server)

        server_layout.addWidget(QLabel("IP :"), 0, 0)
        server_layout.addWidget(self.leIP, 0, 1, 1, 5)
        server_layout.addWidget(QLabel("Port :"), 1, 0)
        server_layout.addWidget(self.lePort, 1, 1, 1, 3)
        server_layout.addWidget(self.bnConnect, 1, 4, 1, 2)

        #&########## Indicator
        self.indicator = QPushButton("")
        self.indicator.setEnabled(False)
        self.indicator.setFixedHeight(120)

        #&########## Status Group
        self.status_group = QGroupBox("General Control")
        status_layout = QGridLayout()
        self.status_group.setLayout(status_layout)
        status_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        row = 0
        status_layout.addWidget(QLabel("Encoder Pos. : "), row, 0)
        self.EncoderPos = QLineEdit()
        self.EncoderPos.setReadOnly(True)
        self.EncoderPos.setStyleSheet("background-color : lightgray")
        status_layout.addWidget(self.EncoderPos, row, 1, 1, 2)

        row += 1
        status_layout.addWidget(QLabel("Encoder mod Pos. : "), row, 0)
        self.EncoderModPos = QLineEdit()
        self.EncoderModPos.setReadOnly(True)
        self.EncoderModPos.setStyleSheet("background-color : lightgray")
        status_layout.addWidget(self.EncoderModPos, row, 1, 1, 2)

        row += 1
        status_layout.addWidget(QLabel("Encoder Rev. : "), row, 0)
        self.EncoderRev = QLineEdit()
        self.EncoderRev.setReadOnly(True)
        self.EncoderRev.setStyleSheet("background-color : lightgray")
        status_layout.addWidget(self.EncoderRev, row, 1, 1, 2)

        row += 1
        status_layout.addWidget(QLabel("Accel. [r/s^2] : "), row, 0)
        self.spAccel = RDoubleSpinBox()
        self.spAccel.setDecimals(3)
        self.spAccel.setSingleStep(0.001)
        self.spAccel.setRange(0.167, 1000.0)
        self.spAccel.returnPressed.connect(self.SetAccel)
        status_layout.addWidget(self.spAccel, row, 1, 1, 2)

        row += 1
        status_layout.addWidget(QLabel("Speed. [r/s] : "), row, 0)
        self.spSpeed = RDoubleSpinBox()
        self.spSpeed.setDecimals(1)
        self.spSpeed.setSingleStep(0.1)
        self.spSpeed.setRange(0.0042, 80.0)
        self.spSpeed.returnPressed.connect(self.SetSpeed)
        status_layout.addWidget(self.spSpeed, row, 1, 1, 2)

        row += 1
        status_layout.addWidget(QLabel("Speed. [rpm] : "), row, 0)
        self.statusSpeed = QLineEdit()
        self.statusSpeed.setReadOnly(True)
        self.statusSpeed.setStyleSheet("background-color : lightgray")
        status_layout.addWidget(self.statusSpeed, row, 1, 1, 2)

        row += 1
        status_layout.addWidget(QLabel("Deaccel. [r/s^2] : "), row, 0)
        self.spDeccel = RDoubleSpinBox()
        self.spDeccel.setDecimals(3)
        self.spDeccel.setSingleStep(0.001)
        self.spDeccel.setRange(0.167, 1000.0)
        self.spDeccel.returnPressed.connect(self.SetDeaccel)
        status_layout.addWidget(self.spDeccel, row, 1, 1, 2)

        row += 1
        self.bnSeekHome = QPushButton("Seek Home")
        status_layout.addWidget(self.bnSeekHome, row, 0, 1, 3)
        self.bnSeekHome.clicked.connect(self.SeekHome)

        row += 1
        status_layout.addWidget(QLabel("Controller Temp. [C] : "), row, 0)
        self.statusTemp = QLineEdit()
        self.statusTemp.setReadOnly(True)
        self.statusTemp.setStyleSheet("background-color : lightgray")
        status_layout.addWidget(self.statusTemp, row, 1, 1, 2)

        row += 1
        status_layout.addWidget(QLabel("Encoder Velocity [rpm] : "), row, 0)
        self.statusEncVel = QLineEdit()
        self.statusEncVel.setReadOnly(True)
        self.statusEncVel.setStyleSheet("background-color : lightgray")
        status_layout.addWidget(self.statusEncVel, row, 1, 1, 2)

        row += 1
        status_layout.addWidget(QLabel("Motor Velocity [rpm]: "), row, 0)
        self.statusMotVel = QLineEdit()
        self.statusMotVel.setReadOnly(True)
        self.statusMotVel.setStyleSheet("background-color : lightgray")
        status_layout.addWidget(self.statusMotVel, row, 1, 1, 2)

        row += 1
        status_layout.addWidget(QLabel("Torque [step] : "), row, 0)
        self.statusTorque = QLineEdit()
        self.statusTorque.setReadOnly(True)
        self.statusTorque.setStyleSheet("background-color : lightgray")
        status_layout.addWidget(self.statusTorque, row, 1, 1, 2)

        row += 1
        self.bnUpdateState = QPushButton("Update Status")
        self.bnUpdateState.clicked.connect(self.Update_Status)
        status_layout.addWidget(self.bnUpdateState, row, 0, 1, 3)

        row += 1
        status_layout.addWidget(QLabel("IO Status : "), row, 0)
        self.ioStatus = QLineEdit()
        self.ioStatus.setReadOnly(True)
        self.ioStatus.setStyleSheet("background-color : lightgray")
        status_layout.addWidget(self.ioStatus, row, 1, 1, 2)

        #&########## Sweeper Control Group
        self.sweep_group = QGroupBox("Veto Sweeper Control")
        sweep_layout = QGridLayout()
        self.sweep_group.setLayout(sweep_layout)
        sweep_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        row = 0
        self.spSpokeWidth = RDoubleSpinBox()
        self.spSpokeWidth.setDecimals(0)
        self.spSpokeWidth.setSingleStep(1)
        self.spSpokeWidth.setRange(0, 511)
        self.spSpokeWidth.returnPressed.connect(self.SetSpokeWidth)
        sweep_layout.addWidget(QLabel("Spoke Width : "), row, 0)
        sweep_layout.addWidget(self.spSpokeWidth, row, 1, 1, 1)

        row += 1
        self.spSpokeOffset = RDoubleSpinBox()
        self.spSpokeOffset.setDecimals(0)
        self.spSpokeOffset.setSingleStep(1)
        self.spSpokeOffset.setRange(-STEP_PER_REVOLUTION, STEP_PER_REVOLUTION )
        self.spSpokeOffset.returnPressed.connect(self.SetSpokeOffset)
        sweep_layout.addWidget(QLabel("Spoke offset : "), row, 0)
        sweep_layout.addWidget(self.spSpokeOffset, row, 1, 1, 1)

        row += 1
        self.spSweepSpeed = RDoubleSpinBox()
        self.spSweepSpeed.setDecimals(2)
        self.spSweepSpeed.setSingleStep(0.25)
        self.spSweepSpeed.setRange(6.0, 1300)
        self.spSweepSpeed.returnPressed.connect(self.SetSweepSpeed)
        sweep_layout.addWidget(QLabel("Speed [rpm] : "), row, 0)
        sweep_layout.addWidget(self.spSweepSpeed, row, 1, 1, 1)

        row += 1
        sweep_layout.addWidget(QLabel("Speed [r/s] : "), row, 0)
        self.statusSweepSpeed = QLineEdit()
        self.statusSweepSpeed.setReadOnly(True)
        self.statusSweepSpeed.setStyleSheet("background-color : lightgray")
        sweep_layout.addWidget(self.statusSweepSpeed, row, 1, 1, 1)

        row += 1
        self.spSweepCutOff = RDoubleSpinBox()
        self.spSweepCutOff.setDecimals(2)
        self.spSweepCutOff.setSingleStep(0.25)
        self.spSweepCutOff.setRange(0.25, 1300)
        self.spSweepCutOff.returnPressed.connect(self.SetSweepCutOff)
        sweep_layout.addWidget(QLabel("Cut Off [rpm] : "), row, 0)
        sweep_layout.addWidget(self.spSweepCutOff, row, 1, 1, 1)

        row += 1
        self.direction_label = QLabel("Only Positive Direction")
        self.direction_label.setStyleSheet("color: blue;")
        self.direction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sweep_layout.addWidget(self.direction_label, row, 0, 1, 2)

        row += 1
        self.sweepStart = QPushButton("Start sweep and spin")
        self.sweepStart.clicked.connect(self.StartSweep)
        sweep_layout.addWidget(self.sweepStart, row, 0, 1, 2)

        row += 1
        self.sweepStop = QPushButton("Stop sweep and spin")
        self.sweepStop.setEnabled(False)
        self.sweepStop.clicked.connect(self.StopSweep)
        sweep_layout.addWidget(self.sweepStop, row, 0, 1, 2)

        #&########## Plot Group
        plot_group = QGroupBox("History Plot")
        plot_layout = QGridLayout()
        plot_group.setLayout(plot_layout)

        btn_layout = QHBoxLayout()
        self.timeWindowButtons = []
        for label, seconds in [("1 min", 60), ("5 min", 300), ("10 min", 600), ("30 min", 1800), ("1 hour", 3600)]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, s=seconds: self.SelectTimeWindow(s))
            self.timeWindowButtons.append(btn)
            btn_layout.addWidget(btn)
        self.timeWindowButtons[0].setChecked(True)
        self.timeWindowButtons[0].setStyleSheet("background-color: green")

        plot_layout.addLayout(btn_layout, 0, 0)

        self.figure = Figure(figsize=(10, 3))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax2 = self.ax.twinx()
        self.figure.tight_layout(pad=2.0)

        plot_layout.addWidget(self.canvas, 1, 0)

        ################################# Add groups to main layout
        main_layout.addWidget(          target_group, 0, 0, 10, 2)

        main_layout.addWidget(          server_group, 0, 2, 2, 1)
        main_layout.addWidget(      self.sweep_group, 2, 2, 8, 1)

        main_layout.addWidget(     self.status_group,  0, 3, 8, 1)
        main_layout.addWidget(        self.indicator,  8, 3, 2, 1)

        main_layout.addWidget(            plot_group, 10, 0, 4, 4)

        self.setLayout(main_layout)


    ################################################################################################################
    def Load_program_setting(self):
        if not os.path.exists("programSettings.json"):
            print("programSettings.json not found, creating default.")
            default = [{"IP": "192.168.0.1", "Port": 7776}]
            with open("programSettings.json", "w") as file:
                json.dump(default, file, indent=2)

        try:
            with open("programSettings.json", "r") as file:
                data = json.load(file)[0]
        except (FileNotFoundError, json.JSONDecodeError, IndexError) as e:
            print(f"Error loading programSettings.json: {e}")
            return

        self.leIP.setText(data.get("IP", "192.168.0.1"))
        self.lePort.setText(str(data.get("Port", 7776)))

    def Save_program_settings(self):
        print(f"Save program settings to programSettings.json")
        try:
            with open("programSettings.json", "r") as file:
                data = json.load(file)[0]
        except (FileNotFoundError, json.JSONDecodeError, IndexError):
            data = {}
        try:
            port = int(self.lePort.text())
        except ValueError:
            port = 7776
        data["IP"] = self.leIP.text()
        data["Port"] = port
        with open("programSettings.json", "w") as file:
            json.dump([data], file, indent=2)

    def Connect_Server(self):
        ip = self.leIP.text().strip()
        port_text = self.lePort.text().strip()
        if not ip or not port_text:
            print("IP or Port is empty, skipping connection.")
            return
        try:
            port = int(port_text)
        except ValueError:
            print(f"Invalid port: '{port_text}'")
            return
        self.controller.Connect(ip, port)
        self.enableSignals = False
        self.Display_Status()
        self.enableSignals = True

    #========================================================================================
    def SetEnableGeneralControl(self, enable):
        self.spAccel.setEnabled(enable)
        self.spDeccel.setEnabled(enable)
        self.spSpeed.setEnabled(enable)
        self.bnSeekHome.setEnabled(enable)
        self.bnUpdateState.setEnabled(enable)

    def setEnableSweepControl(self, enable, myself = False):
        self.sweepStart.setEnabled(enable)
        if myself:
            self.sweepStop.setEnabled(not enable)
        else:
            self.spSpokeWidth.setEnabled(enable)
            self.spSpokeOffset.setEnabled(enable)
            self.spSweepSpeed.setEnabled(enable)
            self.spSweepCutOff.setEnabled(enable)

    def setEnableTargetControl(self, enable):
        for i in range(NTARGET):
            self.target_buttons[i].setEnabled(enable)
            self.target_pos[i].setEnabled(enable)

        self.bnLockPos.setEnabled(enable)
        self.qx4SetPos.setEnabled(enable)

    #========================================================================================
    def Update_Status(self):
        if self.controller.connected:
            self.pauseUpdate = True
            self.controller.getStatus()
            self.Display_Status()
            self.pauseUpdate = False

    def Display_Status(self):
        if self.controller.connected:
            print("Update Status.")

            print(f"Position: {self.controller.position}, Accel: {self.controller.accelRate}, ")
            print(f"Deaccel: {self.controller.deaccelRate}, Speed: {self.controller.velocity}, " +
                  f"Sweep Mask: {bin(self.controller.sweepMask)}")
            print(f"Sweep Offset: {self.controller.spokeOffset}, Spoke Width: {self.controller.spokeWidth}, " +
                   f"Sweep Speed: {self.controller.sweepSpeed}, Sweep Cut Off: {self.controller.sweepCutOff}")

            self.EncoderPos.setText(f"{self.controller.position}")
            self.EncoderModPos.setText(f"{self.controller.position%STEP_PER_REVOLUTION:.0f}")
            self.EncoderRev.setText(f"{self.controller.position/STEP_PER_REVOLUTION:.2f} [rev]")
            self.spAccel.setValue(self.controller.accelRate)
            self.spDeccel.setValue(self.controller.deaccelRate)
            self.spSpeed.setValue(self.controller.velocity)
            self.statusSpeed.setText(f"{self.controller.velocity*60:.1f}")

            self.UpdateButtonsColor()

            #==== sweep parameters
            self.spSpokeWidth.setValue(self.controller.spokeWidth)
            self.spSpokeOffset.setValue(self.controller.spokeOffset)
            self.spSweepSpeed.setValue(self.controller.sweepSpeed)
            self.statusSweepSpeed.setText(f"{self.controller.sweepSpeed/60.:.1f}")
            self.spSweepCutOff.setValue(self.controller.sweepCutOff)
            self.SetTargetPositionBaseOnSpokeOffset()

            self.SetMaxSweepSpeed()

            #=== sweep mask
            for i in range(NTARGET):
                bitPos = 15 - i
                if self.controller.sweepMask & (1 << bitPos):
                    self.target_chkBox[i].setChecked(True)
            if self.controller.sweepMask == (1 << 16) - 1:
                self.isAllSweepEnabled = True
                self.chkAll.setStyleSheet("background-color: green")
                self.chkAll.setText("Disable All")

            #=== other status
            self.statusTemp.setText(f"{self.controller.temperature:.1f}")
            self.statusEncVel.setText(f"{self.controller.encoderVelocity:.2f}")
            self.statusMotVel.setText(f"{self.controller.motorVelocity:.2f}")
            self.statusTorque.setText(f"{self.controller.torque:.2f}")

            #=== QX4
            self.UpdateQX4ParametersFromMemory()

            #=== IO status
            self.ioStatus.setText(bin(int(self.controller.io_status)))

            #=== FW program status
            fw_status = self.controller.FWprogram

            if fw_status > 0 and fw_status < 4:
                print("QX1 sweeping is running.")
                self.SetEnableGeneralControl(False)
                self.setEnableSweepControl(False, True)
                self.setEnableTargetControl(False)

                self.updateTimeInterval = 300
                self.timer.stop()
                self.timer.start(self.updateTimeInterval)

            if fw_status == 4:
                print("QX4 position locking is running. kill it.")
                self.controller.stopQX4LockPosition()

    def UpdateQX4ParametersFromMemory(self):
        if self.controller.connected and self.controller.isQX4Updated:
            self.qx4SetPos.setText(f"{self.controller.qx4EncoderDemandPos}")
            self.controller.isQX4Updated = False

    def UpdateOtherStatus(self):
        if self.controller.connected:
            if self.askPosFromEncoder:
                self.controller.getTemperature(False)
                self.controller.getEncoderVelocity(False)
                self.controller.getMotorVelocity(False)
                self.controller.getTorque(False)
            self.statusTemp.setText(f"{self.controller.temperature:.1f}")
            self.statusEncVel.setText(f"{self.controller.encoderVelocity:.3f}")
            self.statusMotVel.setText(f"{self.controller.motorVelocity:.3f}")
            self.statusTorque.setText(f"{self.controller.torque:.2f}")

    def UpdateButtonsColor(self, tolerance = 10):
        current_pos = self.controller.position

        target_Boundary_width = STEP_PER_REVOLUTION/NTARGET

        for i, pos in enumerate(self.target_pos):
            target_pos = int(pos.text())
            target_pos = self.controller.ConvertModPositionToAbsolute(target_pos)

            if abs(current_pos - target_pos) < target_Boundary_width/2:
                self.target_buttons[i].setStyleSheet("background-color: yellow")
            else:
                self.target_buttons[i].setStyleSheet("")

            if abs(current_pos - target_pos) <= tolerance:
                self.target_buttons[i].setStyleSheet("background-color: green")
                self.button_clicked_id = i

    def Update_Position(self):
        if not self.controller.connected:
            self.indicator.setStyleSheet("background-color: red")
            return

        if not self.pauseUpdate:
            if self.askPosFromEncoder:
                self.controller.getPosition(False)
                self.controller.getIOStatus()
            self.EncoderPos.setText(f"{self.controller.position}")
            self.EncoderModPos.setText(f"{self.controller.position%STEP_PER_REVOLUTION:.0f}")
            self.EncoderRev.setText(f"{self.controller.position/STEP_PER_REVOLUTION:.2f} [rev]")

            self.ioStatus.setText(bin(int(self.controller.io_status)))

            self.UpdateOtherStatus()
            self.UpdateButtonsColor()

            self.history_time.append(time.time())
            self.history_torque.append(self.controller.torque)
            self.history_motor_vel.append(self.controller.motorVelocity)
            self.history_enc_vel.append(self.controller.encoderVelocity)
            self.history_temp.append(self.controller.temperature)

            if self.state == 2:
                enc_vel = self.controller.motorVelocity
                sweep_speed_rps = self.controller.sweepSpeed
                if abs(enc_vel - sweep_speed_rps) < 0.1 * sweep_speed_rps:
                    self.indicator.setStyleSheet("background-color: green")
                else:
                    self.indicator.setStyleSheet("background-color: yellow")
            else:
                self.indicator.setStyleSheet("background-color: blue")

            self.UpdatePlot()
            QApplication.processEvents()

    #======================================================================================== General Control
    def SetAccel(self):
        if self.enableSignals:
            accel = self.spAccel.value()
            self.controller.setAccelRate(accel)
            print(f"Acceleration set to {accel:.3f} [r/s^2]")

    def SetSpeed(self):
        if self.enableSignals:
            speed = self.spSpeed.value()
            self.controller.setVelocity(speed)
            self.statusSpeed.setText(f"{speed*60:.1f} [rpm]")
            print(f"Speed set to {speed:.1f} [r/s] = {speed*60:.1f} [rpm]")

    def SetDeaccel(self):
        if self.enableSignals:
            deaccel = self.spDeccel.value()
            self.controller.setDeaccelRate(deaccel)
            print(f"Deacceleration set to {deaccel:.3f} [r/s^2]")

    def _updatePositionDisplay(self):
        self.EncoderPos.setText(f"{self.controller.position}")
        self.EncoderModPos.setText(f"{self.controller.position%STEP_PER_REVOLUTION:.0f}")
        self.EncoderRev.setText(f"{self.controller.position/STEP_PER_REVOLUTION:.2f} [rev]")

    def CheckPostionStable(self, on_complete=None, wait_time=10, update_interval=200, stable_threshold=5):
        if not self.controller.connected:
            return

        self.pauseUpdate = True
        self._stability_ctx = {
            'start_time': time.time(),
            'old_position': self.controller.position,
            'stable_count': 0,
            'wait_time': wait_time,
            'stable_threshold': stable_threshold,
            'on_complete': on_complete,
        }
        self._stabilityTimer = QTimer(self)
        self._stabilityTimer.timeout.connect(self._checkStabilityTick)
        self._stabilityTimer.start(update_interval)

    def _checkStabilityTick(self):
        ctx = self._stability_ctx
        self.controller.getPosition()
        self._updatePositionDisplay()

        current_position = self.controller.position
        print(f"Current position: {current_position}, Old position: {ctx['old_position']} | count : {ctx['stable_count']}")

        if abs(current_position - ctx['old_position']) < 1:
            ctx['stable_count'] += 1
            if ctx['stable_count'] >= ctx['stable_threshold']:
                print("Position Stable.")
                self._finishStabilityCheck()
                return
        else:
            ctx['stable_count'] = 0
        ctx['old_position'] = current_position

        if time.time() - ctx['start_time'] >= ctx['wait_time']:
            print("Home position not found within timeout.")
            self._finishStabilityCheck()

    def _finishStabilityCheck(self):
        self._stabilityTimer.stop()
        self._stabilityTimer.deleteLater()

        self.controller.getPosition()
        self._updatePositionDisplay()

        self.pauseUpdate = False
        self.updateTimeInterval = DEFAULT_POS_UPDATE_INTERVAL
        self.timer.stop()
        self.timer.start(self.updateTimeInterval)
        print("End of check position stable.")

        on_complete = self._stability_ctx.get('on_complete')
        self._stability_ctx = None
        if on_complete:
            on_complete()

    def SeekHome(self):
        if self.controller.connected:
            self.SetEnableGeneralControl(False)
            self.setEnableSweepControl(False)
            self.state = 4
            self.controller.seekHome()
            self.CheckPostionStable(on_complete=self._onSeekHomeComplete)

    def _onSeekHomeComplete(self):
        self.state = 0
        self.SetEnableGeneralControl(True)
        self.setEnableSweepControl(True)

    def ZeroEncoderPosition(self):
        if self.controller.connected:
            print("Resetting encoder position to 0...")
            self.controller.setEncoderPosition(0)
            time.sleep(0.1)
            self.controller.getPosition()
            self.EncoderPos.setText(f"{self.controller.position}")
            self.EncoderModPos.setText(f"{self.controller.position%STEP_PER_REVOLUTION:.0f}")
            self.EncoderRev.setText(f"{self.controller.position/STEP_PER_REVOLUTION:.2f} [rev]")
            QApplication.processEvents()

    #======================================================================================== Target Control
    def Target_picked(self, id):
        if self.target_buttons[id].isChangeNameMode:
            self.target_names[id] = self.target_buttons[id].name
            print(f"Change Target Name: {self.target_names[id]}, id : {id}")
            QApplication.processEvents()
            return

        QApplication.focusWidget().clearFocus()

        if  self.button_clicked_id != id:
            self.target_buttons[id].setStyleSheet("background-color: green")
            if self.button_clicked_id is not None:
                self.target_buttons[self.button_clicked_id].setStyleSheet("")

            self.button_clicked_id = id

        target_position = int(self.target_pos[id].text())
        self.message.setText(f"Moving to target position {target_position}.")

        if self.isQX4Locking :
            self.qx4SetPos.setText(f"{target_position}")
            self.controller.setQX4EncoderDemandPos(target_position)

        else:
            self.bnLockPos.click()
            time.sleep(1.0)
            self.qx4SetPos.setText(f"{target_position}")
            self.controller.setQX4EncoderDemandPos(target_position)

    def SetPosition(self, id):
        try:
            pos = int(self.target_pos[id].text())
        except ValueError:
            return

        self.target_rev[id].setText(f"{pos / STEP_PER_REVOLUTION:.2f}")

        for i in range(NTARGET):
            if i == 0:
                continue
            idx = (id + i) % NTARGET
            pp = pos + STEP_PER_REVOLUTION/NTARGET * i
            if pp >= STEP_PER_REVOLUTION:
                pp -= STEP_PER_REVOLUTION
            self.target_pos[idx].setText(f"{int(pp)}")
            self.target_rev[idx].setText(f"{pp / STEP_PER_REVOLUTION:.2f}")

        if self.isQX4Locking:
            self.qx4SetPos.setText(f"{pos}")
            self.controller.setQX4EncoderDemandPos(int(pos))

    def Sweep_picked(self, id):
        self.timer.stop()
        print("Old Sweep Mask: %s | 0x%04X | %d" % (bin(self.controller.sweepMask), self.controller.sweepMask, self.controller.sweepMask ))
        bitPos = 15 - id
        if self.target_chkBox[id].isChecked():
            print(f"Sweep Target : {self.target_names[id]}, id : {id}")
            self.controller.sweepMask |= (1 << bitPos)
        else:
            print(f"Uncheck Sweep Target : {self.target_names[id]}, id : {id}")
            self.controller.sweepMask &= ~(1 << bitPos)

        print("New Sweep Mask: %s | 0x%04X | %d" % (bin(self.controller.sweepMask), self.controller.sweepMask, self.controller.sweepMask))

        if self.isAllSweepEnabled:
            self.isAllSweepEnabled = False
            self.chkAll.setStyleSheet("")
            self.chkAll.setText("Enable All")

        self.controller.setSweepMask(self.controller.sweepMask)
        time.sleep(0.1)
        self.timer.start(self.updateTimeInterval)

    def setAllSweepTargets(self):
        self.timer.stop()
        self.enableSignals = False
        if not self.isAllSweepEnabled:
            self.isAllSweepEnabled = True
            self.chkAll.setStyleSheet("background-color: green")
            self.chkAll.setText("Disable All")
            for i in range(NTARGET):
                self.target_chkBox[i].setChecked(True)
            tempMask = (1 << 16) - 1
            self.controller.setSweepMask(tempMask)
        else:
            self.isAllSweepEnabled = False
            print("Uncheck all targets from sweep.")
            self.chkAll.setStyleSheet("")
            self.chkAll.setText("Enable All")
            for i in range(NTARGET):
                self.target_chkBox[i].setChecked(False)
            self.controller.setSweepMask(0)
        self.enableSignals = True
        time.sleep(0.1)
        self.timer.start(self.updateTimeInterval)

    def LockPosition(self):
        if self.controller.connected:

            if not self.isQX4Locking:
                self.isQX4Locking = True
                self.bnLockPos.setStyleSheet("background-color: green")

                self.controller.startQX4LockPosition()

                time.sleep(0.5)
                self.UpdateQX4ParametersFromMemory()

                self.SetEnableGeneralControl(False)
                self.setEnableSweepControl(False)

                self.state = 3

            else:
                self.isQX4Locking = False
                self.bnLockPos.setStyleSheet("")

                self.controller.stopQX4LockPosition()
                self.UpdateQX4ParametersFromMemory()

                self.SetEnableGeneralControl(True)
                self.setEnableSweepControl(True)

                self.state = 0

    #======================================================================================== Sweep Control
    def SetMaxSweepSpeed(self):
        maxSpeed1 = 60. / 0.0536 * (1 - self.spSpokeWidth.value() / 512)
        maxSpeed2 = 60. / 0.0044 * (self.spSpokeWidth.value() / 512)
        maxSpeed = min(maxSpeed1, maxSpeed2)
        maxSpeed = math.floor(maxSpeed / 0.25) * 0.25
        self.spSweepSpeed.setMaximum(maxSpeed)
        self.spSweepSpeed.setStyleSheet("color: black;")
        print(f"Spoke Width set to {self.spSpokeWidth.value():.0f}, max sweep speed: {maxSpeed:.2f} rpm")

    def SetSpokeWidth(self):
        if self.enableSignals:
            self.controller.setSpokeWidth(self.spSpokeWidth.value())
            self.SetMaxSweepSpeed()

    def SetSpokeOffset(self):
        if self.enableSignals:
            self.controller.setSpokeOffset(self.spSpokeOffset.value())
            self.SetTargetPositionBaseOnSpokeOffset()

    def SetTargetPositionBaseOnSpokeOffset(self):
        offset = self.spSpokeOffset.value()
        for i in range(NTARGET):
            base_pos = int(STEP_PER_REVOLUTION/NTARGET * i)
            new_pos = base_pos + offset - STEP_PER_REVOLUTION/ (2*NTARGET)
            if new_pos < 0:
                new_pos += STEP_PER_REVOLUTION
            elif new_pos >= STEP_PER_REVOLUTION:
                new_pos -= STEP_PER_REVOLUTION
            self.target_pos[i].setText(f"{int(new_pos)}")
            self.target_rev[i].setText(f"{new_pos / STEP_PER_REVOLUTION:.3f}")

    def SetSweepSpeed(self):
        if self.enableSignals:
            self.controller.setSweepSpeed( self.spSweepSpeed.value())
            self.statusSweepSpeed.setText(f"{self.spSweepSpeed.value()/60.:.3f}")

    def SetSweepCutOff(self):
        if self.enableSignals:
            self.controller.setSweepCutOff(self.spSweepCutOff.value())

    def StartSweep(self):
        if self.controller.connected:
            self.SetEnableGeneralControl(False)
            self.setEnableSweepControl(False, True)
            self.setEnableTargetControl(False)

            self.state = 2

            self.controller.send_message("DI100")
            self.controller.startSpinSweep()

            self.updateTimeInterval = 300
            self.timer.stop()
            self.timer.start(self.updateTimeInterval)

    def StopSweep(self):
        if self.controller.connected:
            origin_speed = self.controller.sweepSpeed
            self.controller.stopSpinSweep()

            self.direction_label.setText("Stopping... Please wait")
            self.direction_label.setStyleSheet("color: red;")

            self.timer.stop()

            while True:
                old_velocity = self.controller.motorVelocity
                self.Update_Position()
                new_velocity = self.controller.motorVelocity
                status = int(self.controller.io_status) & 0b111
                print(f"Waiting for sweep to stop... IO status: {status:03b}")

                if status  == 7:
                    self.controller.isSpinning = False
                    break

                if new_velocity > 1 and abs(new_velocity - old_velocity) < 0.1:
                    print("Velocity not changing, forcing stop.")
                    break

                time.sleep(0.3)
                QApplication.processEvents()

            self.controller.send_message("SK")
            self.controller.send_message('IO7')
            self.controller.send_message('RLO0')
            self.controller.setSweepSpeed(origin_speed)

            self.direction_label.setStyleSheet("color: blue;")
            self.direction_label.setText("Only Positive Direction")

            self.state = 0

            self.Update_Status()

            self.SetEnableGeneralControl(True)
            self.setEnableSweepControl(True, True)
            self.setEnableTargetControl(True)

            self.updateTimeInterval = DEFAULT_POS_UPDATE_INTERVAL
            self.timer.stop()
            self.timer.start(self.updateTimeInterval)

            self.UpdateButtonsColor()

    #======================================================================================== QX4 Control
    def SetQX4Position(self):
        if self.enableSignals:
            pos = int(self.qx4SetPos.text())
            self.controller.setQX4EncoderDemandPos(pos)

    #======================================================================================== Plot
    def SelectTimeWindow(self, seconds):
        self.selectedTimeWindow = seconds
        for btn in self.timeWindowButtons:
            btn.setChecked(False)
            btn.setStyleSheet("")
        sender = self.sender()
        if sender:
            sender.setChecked(True)
            sender.setStyleSheet("background-color: green")
        self.UpdatePlot()

    def UpdatePlot(self):
        if len(self.history_time) < 2:
            return

        now = time.time()
        cutoff = now - self.selectedTimeWindow

        t = list(self.history_time)
        start_idx = 0
        for i, ts in enumerate(t):
            if ts >= cutoff:
                start_idx = i
                break

        times = [t[i] - now for i in range(start_idx, len(t))]
        torque = list(self.history_torque)[start_idx:]
        motor_vel = list(self.history_motor_vel)[start_idx:]
        enc_vel = list(self.history_enc_vel)[start_idx:]
        temp = list(self.history_temp)[start_idx:]

        self.ax.clear()
        self.ax2.clear()

        self.ax.plot(times, torque, 'r-', label='Torque [step]', linewidth=0.8)
        self.ax.plot(times, motor_vel, 'b-', label='Motor Vel [rpm]', linewidth=0.8)
        self.ax.plot(times, enc_vel, 'g-', label='Encoder Vel [rpm]', linewidth=0.8)
        self.ax2.plot(times, temp, color='gray', linestyle='-', label='Temp [°C]', linewidth=0.8)

        self.ax.set_xlabel("Time [s]")
        self.ax.set_ylabel("Torque / Velocity")
        self.ax2.set_ylabel("Temperature [°C]")

        lines1, labels1 = self.ax.get_legend_handles_labels()
        lines2, labels2 = self.ax2.get_legend_handles_labels()
        self.ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=7)

        self.ax.grid(True, alpha=0.3)
        self.figure.tight_layout(pad=1.5)
        self.canvas.draw_idle()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TargetWheelControlSimple()
    window.show()
    sys.exit(app.exec())
