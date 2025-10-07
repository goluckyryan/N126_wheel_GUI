#!/usr/bin/env python3

import sys
import json
import math
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QGridLayout,
    QGroupBox, QLabel,  QFileDialog, QCheckBox, QLineEdit, QDoubleSpinBox,
    QApplication, QComboBox, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QCloseEvent
import time

from Library import Controller, STEP_PER_REVOLUTION
from PyQt6.QtWidgets import QSpacerItem, QSizePolicy

NTARGET = 16
DAEFUL_POS_UPDATE_INTERVAL = 1000  # milliseconds


class TargetButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.isChangeNameMode = False
        self.name = text
        # self.setStyleSheet("background-color : #EDA6E5")
    
    def mousePressEvent(self, event):
        # Check for Ctrl + Left-click
        # if event.button() == Qt.MouseButton.LeftButton and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
        if event.button() == Qt.MouseButton.RightButton :
            # Open input dialog to get new button title
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
            # Call the original mousePressEvent for normal behavior
            self.isChangeNameMode = False

        super().mousePressEvent(event)

#########################################################################################################
#########################################################################################################
#########################################################################################################
#########################################################################################################
class TargetWheelControl(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Target Wheel Control")
        # self.setStyleSheet("background-color : #FFD7FB")
        self.target_buttons = []
        self.target_chkBox = []
        self.target_pos = []
        self.target_rev = []
        self.target_names = [f"Target {i}" for i in range(16)]
        self.fileName = None

        self.button_clicked_id = None # which target button is clicked

        self.controller = Controller()

        self.init_ui()

        self.Load_program_setting()
        self.Connect_Server()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.Update_Position)
        self.updateTimeInterval = DAEFUL_POS_UPDATE_INTERVAL  # milliseconds
        self.timer.start(self.updateTimeInterval) 
        self.pauseUpdate = False
        self.askPosFromEncoder = True

        self.isQX4Locking = False

    def closeEvent(self, event: QCloseEvent):
        if self.fileName is None or self.fileName == "":
            self.save_targets_click()
        else:
            self.save_targets_info()
        self.Save_program_settings()
        self.controller.send_message("SK")
        self.controller.disconnect()
        event.accept()  # Optional: confirm you want to close
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
            target_layout.addWidget(le, row, 5, 1, 2)

            le2 = QLineEdit(str(int(STEP_PER_REVOLUTION/NTARGET)*i/STEP_PER_REVOLUTION))
            le2.setReadOnly(True)
            le2.setEnabled(False)
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

        # Lock Pos. 
        row += 1
        target_layout.addWidget(QLabel("Set Position : "), row, 1, 1, 3)
        self.qx4SetPos = QLineEdit("0")
        self.qx4SetPos.setFixedWidth(60)
        self.qx4SetPos.returnPressed.connect(self.SetQX4Position)
        target_layout.addWidget(self.qx4SetPos, row, 4, 1, 1)

        self.bnLockPos = QPushButton("Lock Position")
        target_layout.addWidget(self.bnLockPos, row, 5, 1, 5)
        self.bnLockPos.clicked.connect(self.LockPosition)

        row += 1
        target_layout.addWidget(QLabel("Cntrl. update [100us] : "), row, 1, 1, 3)
        self.qx4UpdateInterval = QLineEdit("1000")
        self.qx4UpdateInterval.setFixedWidth(60)
        self.qx4UpdateInterval.returnPressed.connect(self.SetQX4UpdateInterval)
        target_layout.addWidget(self.qx4UpdateInterval, row, 4, 1, 1)

        target_layout.addWidget(QLabel("Slew Speed [0.25 rpm] : "), row, 5)
        self.qx4SlewSpeed = QLineEdit("40")
        self.qx4SlewSpeed.returnPressed.connect(self.SetQX4SlewSpeed)
        target_layout.addWidget(self.qx4SlewSpeed, row, 7, 1, 3)

        row += 1
        target_layout.addWidget(QLabel("Motor demand pos. : "), row, 1, 1, 3)
        self.qx4MotorPos = QLineEdit("0")
        self.qx4MotorPos.setFixedWidth(60)
        self.qx4MotorPos.setReadOnly(True)
        self.qx4MotorPos.setStyleSheet("background-color : lightgray")
        target_layout.addWidget(self.qx4MotorPos, row, 4, 1, 1)        

        target_layout.addWidget(QLabel("Servo speed [0.25 rpm] : "), row, 5)
        self.qx4ServoSpeed = QLineEdit("20")
        self.qx4ServoSpeed.returnPressed.connect(self.SetQX4ServoSpeed)
        target_layout.addWidget(self.qx4ServoSpeed, row, 7, 1, 3)


        #@===================== Add a vertical spacer to push following widgets down
        # row += 1
        # target_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding), row, 0, 1, 10)

        # Load/Save Buttons
        row += 1
        load_button = QPushButton("Load Targets")
        save_button = QPushButton("Save Targets")
        load_button.clicked.connect(self.load_targets_click)
        save_button.clicked.connect(self.save_targets_click)
        target_layout.addWidget(load_button, row, 1, 1, 2)
        target_layout.addWidget(save_button, row, 3, 1, 2)

        # row += 1
        self.fileNameLineEdit = QLineEdit("")
        self.fileNameLineEdit.setReadOnly(True)
        target_layout.addWidget(self.fileNameLineEdit, row, 5, 1, 5)

        #&########## Server 
        server_group = QGroupBox("Server")
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


        #&########## Status Group
        self.status_group = QGroupBox("General Control")
        status_layout = QGridLayout()
        self.status_group.setLayout(status_layout)
        status_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # row = 0
        # status_layout.addWidget(self.connectionStatus, row, 0, 1, 3)

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
        self.spAccel = QDoubleSpinBox()
        self.spAccel.setDecimals(3)
        self.spAccel.setSingleStep(0.001)
        self.spAccel.setRange(0.167, 1000.0)
        self.spAccel.valueChanged.connect(self.SetAccel)
        status_layout.addWidget(self.spAccel, row, 1, 1, 2)

        row += 1
        status_layout.addWidget(QLabel("Speed. [r/s] : "), row, 0)
        self.spSpeed = QDoubleSpinBox()
        self.spSpeed.setDecimals(1)
        self.spSpeed.setSingleStep(0.1)
        self.spSpeed.setRange(0.0042, 80.0)
        self.spSpeed.valueChanged.connect(self.SetSpeed)
        status_layout.addWidget(self.spSpeed, row, 1, 1, 2)

        row += 1
        status_layout.addWidget(QLabel("Speed. [rpm] : "), row, 0)
        self.statusSpeed = QLineEdit()
        self.statusSpeed.setReadOnly(True)
        self.statusSpeed.setStyleSheet("background-color : lightgray")
        status_layout.addWidget(self.statusSpeed, row, 1, 1, 2)

        row += 1
        status_layout.addWidget(QLabel("Deaccel. [r/s^2] : "), row, 0)
        self.spDeccel = QDoubleSpinBox()
        self.spDeccel.setDecimals(3)
        self.spDeccel.setSingleStep(0.001)
        self.spDeccel.setRange(0.167, 1000.0)
        self.spDeccel.valueChanged.connect(self.SetDeaccel)
        status_layout.addWidget(self.spDeccel, row, 1, 1, 2)

        row += 1
        self.bnSeekHome = QPushButton("Seek Home")
        status_layout.addWidget(self.bnSeekHome, row, 0, 1, 3)
        self.bnSeekHome.clicked.connect(self.SeekHome)

        row += 1
        self.bnZeroEncoderPosition = QPushButton("Zero Encoder Position")
        status_layout.addWidget(self.bnZeroEncoderPosition, row, 0, 1, 3)
        self.bnZeroEncoderPosition.clicked.connect(self.ZeroEncoderPosition)

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


        #&########## manual command group
        self.manual_group = QGroupBox("Manual Command")
        manual_layout = QGridLayout()
        self.manual_group.setLayout(manual_layout)
        manual_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        row = 0
        self.leSendMsg = QLineEdit()
        self.leSendMsg.returnPressed.connect(self.Send_Message)
        manual_layout.addWidget(QLabel("Send CMD : "), row, 0)
        manual_layout.addWidget(self.leSendMsg, row, 1, 1, 2)

        row += 1
        self.leGetMsg = QLineEdit()
        self.leGetMsg.setReadOnly(True)
        manual_layout.addWidget(QLabel("Reply : "), row, 0)
        manual_layout.addWidget(self.leGetMsg, row, 1, 1, 2)


        #&########## Spinning Control Group
        self.spin_group = QGroupBox("Spinning Control")
        spin_layout = QGridLayout()
        self.spin_group.setLayout(spin_layout)
        spin_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        row = 0
        self.spSpinSpeed = QDoubleSpinBox()
        self.spSpinSpeed.setDecimals(2)
        self.spSpinSpeed.setSingleStep(0.1)
        self.spSpinSpeed.setRange(0.0042, 80.0)
        spin_layout.addWidget(QLabel("Spin Speed [r/s] : "), row, 0)
        spin_layout.addWidget(self.spSpinSpeed, row, 1, 1, 2)
        self.spSpinSpeed.valueChanged.connect(self.SetSpinSpeed)

        row += 1
        spin_layout.addWidget(QLabel("Spin speed [rpm]"), row, 0)
        self.statusSpinSpeed = QLineEdit()
        self.statusSpinSpeed.setReadOnly(True)
        self.statusSpinSpeed.setStyleSheet("background-color : lightgray")
        spin_layout.addWidget(self.statusSpinSpeed, row, 1, 1, 2)

        row += 1
        self.spSpinAccel = QDoubleSpinBox()
        self.spSpinAccel.setDecimals(3)
        self.spSpinAccel.setSingleStep(0.1)
        self.spSpinAccel.setRange(0.167, 1000.0)
        spin_layout.addWidget(QLabel("Spin Accel. [r/s^2] : "), row, 0)
        spin_layout.addWidget(self.spSpinAccel, row, 1, 1, 2)
        self.spSpinAccel.valueChanged.connect(self.SetSpinAccel)

        row += 1
        self.cbDirection = QComboBox()
        self.cbDirection.addItems(["Clockwise (+)", "Counterclockwise (-)"])
        spin_layout.addWidget(QLabel("Direction : "), row, 0)
        spin_layout.addWidget(self.cbDirection, row, 1, 1, 2)

        row += 1
        self.bnSpinStart = QPushButton("Start Spin")
        spin_layout.addWidget(self.bnSpinStart, row, 0, 1, 3)
        self.bnSpinStart.clicked.connect(self.StartSpin)

        row += 1
        self.bnSpinStop = QPushButton("Stop Spin")
        spin_layout.addWidget(self.bnSpinStop, row, 0, 1, 3)
        self.bnSpinStop.clicked.connect(self.StopSpin)
        self.bnSpinStop.setEnabled(False)
 
        #&########## Sweeper Control Group
        self.sweep_group = QGroupBox("Veto Sweeper Control")
        sweep_layout = QGridLayout()
        self.sweep_group.setLayout(sweep_layout)
        sweep_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        row = 0
        self.spSpokeWidth = QDoubleSpinBox()
        self.spSpokeWidth.setDecimals(0)
        self.spSpokeWidth.setSingleStep(1)
        self.spSpokeWidth.setRange(0, 511)
        self.spSpokeWidth.valueChanged.connect(self.SetSpokeWidth)
        sweep_layout.addWidget(QLabel("Spoke Width : "), row, 0)
        sweep_layout.addWidget(self.spSpokeWidth, row, 1, 1, 1)

        row += 1
        self.spSpokeOffset = QDoubleSpinBox()
        self.spSpokeOffset.setDecimals(0)
        self.spSpokeOffset.setSingleStep(1)
        self.spSpokeOffset.setRange(-STEP_PER_REVOLUTION, STEP_PER_REVOLUTION )
        self.spSpokeOffset.valueChanged.connect(self.SetSpokeOffset)
        sweep_layout.addWidget(QLabel("Spoke offset : "), row, 0)
        sweep_layout.addWidget(self.spSpokeOffset, row, 1, 1, 1)
 
        row += 1
        self.spSweepSpeed = QDoubleSpinBox()
        self.spSweepSpeed.setDecimals(2)
        self.spSweepSpeed.setSingleStep(0.25)
        self.spSweepSpeed.setRange(6.0, 1300)
        self.spSweepSpeed.valueChanged.connect(self.SetSweepSpeed)
        sweep_layout.addWidget(QLabel("Speed [rpm] : "), row, 0)
        sweep_layout.addWidget(self.spSweepSpeed, row, 1, 1, 1)

        row += 1
        sweep_layout.addWidget(QLabel("Speed [r/s] : "), row, 0)
        self.statusSweepSpeed = QLineEdit()
        self.statusSweepSpeed.setReadOnly(True)
        self.statusSweepSpeed.setStyleSheet("background-color : lightgray")
        sweep_layout.addWidget(self.statusSweepSpeed, row, 1, 1, 1)
 
        row += 1
        self.spSweepCutOff = QDoubleSpinBox()
        self.spSweepCutOff.setDecimals(2)
        self.spSweepCutOff.setSingleStep(0.25)
        self.spSweepCutOff.setRange(0.25, 1300)
        self.spSweepCutOff.valueChanged.connect(self.SetSweepCutOff)
        sweep_layout.addWidget(QLabel("Cut Off [rpm] : "), row, 0)
        sweep_layout.addWidget(self.spSweepCutOff, row, 1, 1, 1)
 
        row += 1
        self.direction_label = QLabel("Only Positive Direction")
        # direction_label.setStyleSheet("color: blue; font-weight: bold;")
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

       

        ################################# Add groups to main layout
        main_layout.addWidget(          target_group, 0, 0, 6, 2)

        main_layout.addWidget(     self.status_group, 0, 2, 5, 1)
        main_layout.addWidget(     self.manual_group, 5, 2, 1, 1)

        main_layout.addWidget(          server_group, 0, 3, 1, 1)
        main_layout.addWidget(       self.spin_group, 1, 3, 2, 1)
        main_layout.addWidget(      self.sweep_group, 3, 3, 3, 1)


        self.setLayout(main_layout)


    ################################################################################################################
    ################################################################################################################
    ################################################################################################################
    def Load_program_setting(self):
        with open("programSettings.json", "r") as file:
            data = json.load(file)[0]
            self.leIP.setText(data["IP"])
            self.lePort.setText(str(data["Port"]))

            self.fileName = data["target_file"]
            self.fileNameLineEdit.setText(self.fileName)
            self.load_targets_info()

    def Save_program_settings(self):
        print(f"Save program settings to programSettings.json")
        data = [{"IP": self.leIP.text(), "Port": int(self.lePort.text()), "target_file" : self.fileName}]
        with open("programSettings.json", "w") as file:
            json.dump(data, file, indent=2)

    def Connect_Server(self):
        self.controller.Connect(self.leIP.text(), int(self.lePort.text()))
        self.enableSignals = False  # Disable signals-slots during connection
        self.Display_Status()
        self.enableSignals = True  # Enable signals-slots after connection

    #========================================================================================
    def SetEnableGeneralControl(self, enable):
        self.spAccel.setEnabled(enable)
        self.spDeccel.setEnabled(enable)
        self.spSpeed.setEnabled(enable)
        self.bnSeekHome.setEnabled(enable)
        self.bnZeroEncoderPosition.setEnabled(enable)
        self.bnUpdateState.setEnabled(enable)

    def setEnableSpinControl(self, enable, myself = False):
        self.spSpinSpeed.setEnabled(enable)
        self.spSpinAccel.setEnabled(enable)
        self.cbDirection.setEnabled(enable)
        self.bnSpinStart.setEnabled(enable)
        if myself:
            self.bnSpinStop.setEnabled(not enable)

    def setEnableSweepControl(self, enable, myself = False):
        self.sweepStart.setEnabled(enable)
        if myself:
            self.sweepStop.setEnabled(not enable)
        else:
            self.spSpokeWidth.setEnabled(enable)
            self.spSpokeWidth.setEnabled(enable)
            self.spSweepSpeed.setEnabled(enable)
            self.spSweepCutOff.setEnabled(enable)

    def setEnableTargetControl(self, enable):
        for i in range(NTARGET):
            self.target_buttons[i].setEnabled(enable)
            self.target_pos[i].setEnabled(enable)
        
        self.bnLockPos.setEnabled(enable)
        self.qx4SetPos.setEnabled(enable)
        self.qx4UpdateInterval.setEnabled(enable)
        self.qx4SlewSpeed.setEnabled(enable)
        self.qx4ServoSpeed.setEnabled(enable)
        # if all:
        #     self.chkAll.setEnabled(enable)
        #     for i in range(NTARGET):
        #         self.target_chkBox[i].setEnabled(enable)

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
                  f"Move Distance: {self.controller.moveDistance}, Jog Speed: {self.controller.jogSpeed}, " +
                  f"Jog Accel: {self.controller.jogAccel}, Sweep Mask: {bin(self.controller.sweepMask)}")
            print(f"Sweep Offset: {self.controller.spokeOffset}, Spoke Width: {self.controller.spokeWidth}, " +  
                   f"Sweep Speed: {self.controller.sweepSpeed}, Sweep Cut Off: {self.controller.sweepCutOff}")

            self.EncoderPos.setText(f"{self.controller.position}")
            self.EncoderModPos.setText(f"{self.controller.position%STEP_PER_REVOLUTION:.0f}")
            self.EncoderRev.setText(f"{self.controller.position/STEP_PER_REVOLUTION:.2f} [rev]")
            self.spAccel.setValue(self.controller.accelRate)
            self.spDeccel.setValue(self.controller.deaccelRate)
            self.spSpeed.setValue(self.controller.velocity)
            self.statusSpeed.setText(f"{self.controller.velocity*60:.1f}")

            self.spSpinSpeed.setValue(self.controller.jogSpeed)
            self.statusSpinSpeed.setText(f"{self.controller.jogSpeed*60:.1f}")
            self.spSpinAccel.setValue(self.controller.jogAccel)
            if self.controller.moveDistance >= 0 :
                self.cbDirection.setCurrentIndex(0)  # Clockwise
            else:
                self.cbDirection.setCurrentIndex(1)

            self.spSpinAccel.setStyleSheet("")

            #=== check current position and set the corresponding 
            self.UpdateButtonsColor()

            #==== sweep parameters
            self.spSpokeWidth.setValue(self.controller.spokeWidth)
            self.spSpokeOffset.setValue(self.controller.spokeOffset)
            self.spSweepSpeed.setValue(self.controller.sweepSpeed)
            self.statusSweepSpeed.setText(f"{self.controller.sweepSpeed/60.:.1f}")
            self.spSweepCutOff.setValue(self.controller.sweepCutOff)

            self.SetMaxSweepSpeed()

            #=== sweep mask
            for i in range(NTARGET):
                bitPos = 15 - i
                if self.controller.sweepMask & (1 << bitPos):
                    self.target_chkBox[i].setChecked(True)
            if self.controller.sweepMask == (1 << 16) - 1:
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

            if fw_status > 0 and fw_status < 4: # QX1 is running, i.e. the sweeping is on
                print("QX1 sweeping is running.")
                self.SetEnableGeneralControl(False)
                self.setEnableSpinControl(False)
                self.setEnableSweepControl(False, True)
                self.setEnableTargetControl(False)

                self.updateTimeInterval = 300  # milliseconds
                self.timer.stop()
                self.timer.start(self.updateTimeInterval)

            if fw_status == 4: # QX4 is running, i.e. the position locking is on
                print("QX4 position locking is running. kill it.")
                self.controller.stopQX4LockPosition()

    def UpdateQX4ParametersFromMemory(self):
        if self.controller.connected and self.controller.isQX4Updated:
            self.qx4SetPos.setText(f"{self.controller.qx4EncoderDemandPos}")
            self.qx4UpdateInterval.setText(f"{self.controller.qx4ControUpdate}")
            self.qx4SlewSpeed.setText(f"{self.controller.qx4SlewSpeed}")
            self.qx4ServoSpeed.setText(f"{self.controller.qx4ServoSlewSpeed}")
            self.qx4MotorPos.setText(f"{self.controller.qx4MotorDemandPos}")
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

    def UpdateButtonsColor(self, tolerance = 10): # step
        current_pos = self.controller.position #absolute position
        # print(f"Current absolute position: {current_pos}, mod: {current_pos%STEP_PER_REVOLUTION:.0f}")
        
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

    def Update_Position(self): # see self.updateTimeInterval
        if self.pauseUpdate == False:
            if self.askPosFromEncoder:
                self.controller.getPosition(False)
                self.controller.getIOStatus()
            self.EncoderPos.setText(f"{self.controller.position}") 
            self.EncoderModPos.setText(f"{self.controller.position%STEP_PER_REVOLUTION:.0f}")
            self.EncoderRev.setText(f"{self.controller.position/STEP_PER_REVOLUTION:.2f} [rev]")

            self.ioStatus.setText(bin(int(self.controller.io_status)))

            self.UpdateOtherStatus()
            #if ModPos is close to a target, change the button color
            self.UpdateButtonsColor()
            # self.UpdateStateButtons()

            QApplication.processEvents()  # Process events to update the UI


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

    def CheckPostionStable(self, wait_time=10, update_interval=0.2, stable_threshold=5):
        if self.controller.connected:
    
            self.pauseUpdate = True  

            start_time = time.time()
            old_position = self.controller.position
            stableCount  = 0
            while time.time() - start_time < wait_time:
                time.sleep(update_interval)  
                self.controller.getPosition()
                self.EncoderPos.setText(f"{self.controller.position}") 
                self.EncoderModPos.setText(f"{self.controller.position%STEP_PER_REVOLUTION:.0f}")
                self.EncoderRev.setText(f"{self.controller.position/STEP_PER_REVOLUTION:.2f} [rev]")
                QApplication.processEvents()  # Process events to update the UI
                current_position = self.controller.position
                print(f"Current position: {current_position}, Old position: {old_position} | count : {stableCount}")
                if abs(current_position - old_position) < 1:
                    stableCount += 1
                    if stableCount >= stable_threshold:
                        print("Position Stable.") 
                        break
                else:
                    stableCount = 0
                old_position = current_position
            else:
                print("Home position not found within 10 seconds. ")

            time.sleep(0.2)  # Wait a bit to ensure the command is processed   
            self.controller.getPosition()
            self.EncoderPos.setText(f"{self.controller.position}") 
            self.EncoderModPos.setText(f"{self.controller.position%STEP_PER_REVOLUTION:.0f}")
            self.EncoderRev.setText(f"{self.controller.position/STEP_PER_REVOLUTION:.2f} [rev]")      
            QApplication.processEvents()  # Process events to update the UI

            self.pauseUpdate = False
            self.updateTimeInterval = DAEFUL_POS_UPDATE_INTERVAL 
            self.timer.stop()
            self.timer.start(self.updateTimeInterval)  # Restart the timer with the new interval
            print("End of check position stable.")

    def SeekHome(self):
        if self.controller.connected:
            self.SetEnableGeneralControl(False)
            self.setEnableSpinControl(False)
            self.setEnableSweepControl(False)
            self.controller.seekHome()
            self.CheckPostionStable()
            self.SetEnableGeneralControl(True)
            self.setEnableSpinControl(True)
            self.setEnableSweepControl(True)
            
    def ZeroEncoderPosition(self):
        if self.controller.connected:
            print("Resetting encoder position to 0...")
            self.controller.setEncoderPosition(0)  # Set the encoder position to 0
            time.sleep(0.1)  
            self.controller.getPosition()
            self.EncoderPos.setText(f"{self.controller.position}") 
            self.EncoderModPos.setText(f"{self.controller.position%STEP_PER_REVOLUTION:.0f}")
            self.EncoderRev.setText(f"{self.controller.position/STEP_PER_REVOLUTION:.2f} [rev]")
            QApplication.processEvents()  # Process events to update the UI


    def Send_Message(self):
        self.timer.stop()  # Stop the timer to prevent updates during message sending
        self.leGetMsg.setText(self.controller.send_message(self.leSendMsg.text()))
        self.leSendMsg.selectAll()
        time.sleep(0.1)  # Wait a bit to ensure the command is processed
        self.timer.start(self.updateTimeInterval)  # Restart the timer with the original interval

    #======================================================================================== Target Control
    def Target_picked(self, id):
        if self.target_buttons[id].isChangeNameMode:
            self.target_names[id] = self.target_buttons[id].name
            print(f"Change Target Name: {self.target_names[id]}, id : {id}")
            QApplication.processEvents()  # Process events to update the UI
            return

        # Remove focus from all buttons after click
        QApplication.focusWidget().clearFocus()

        #=== change color
        if  self.button_clicked_id != id:
            self.target_buttons[id].setStyleSheet("background-color: green")
            if self.button_clicked_id != None:
                self.target_buttons[self.button_clicked_id].setStyleSheet("")

            self.button_clicked_id = id

        target_position = int(self.target_pos[id].text())
        self.message.setText(f"Moving to target position {target_position}.")
        
        if self.isQX4Locking :
            self.qx4SetPos.setText(f"{target_position}")
            self.controller.setQX4EncoderDemandPos(target_position)

        else: #start QX4 locking
            self.bnLockPos.click()
            time.sleep(1.0)  # Wait a bit to ensure the command is processed
            self.qx4SetPos.setText(f"{target_position}")
            self.controller.setQX4EncoderDemandPos(target_position)


    def SetPosition(self, id):
        # print(f"Set Position for Target {id}: {self.target_pos[id].text()}")
        if self.target_pos[id].text().isdigit():
            pos = int(self.target_pos[id].text())
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

            if self.isQX4Locking :
                self.qx4SetPos.setText(f"{pos}")
                self.controller.setQX4EncoderDemandPos(int(pos))

    def Sweep_picked(self, id):
        self.timer.stop()  # Stop the timer to prevent updates during sweep selection
        print("Old Sweep Mask: %s | 0x%04X | %d" % (bin(self.controller.sweepMask), self.controller.sweepMask, self.controller.sweepMask ))
        bitPos = 15 - id
        if self.target_chkBox[id].isChecked():
            print(f"Sweep Target : {self.target_names[id]}, id : {id}")
            self.controller.sweepMask |= (1 << bitPos)  # Set the bit for the target
        else:
            print(f"Uncheck Sweep Target : {self.target_names[id]}, id : {id}")
            self.controller.sweepMask &= ~(1 << bitPos)  # Unset the bit for the target

        print("New Sweep Mask: %s | 0x%04X | %d" % (bin(self.controller.sweepMask), self.controller.sweepMask, self.controller.sweepMask))

        if self.chkAll.styleSheet() == "background-color: green":
            self.chkAll.setStyleSheet("")  # Uncheck the "All" button if it was checked
            self.chkAll.setText("Enable All")

        self.controller.setSweepMask(self.controller.sweepMask)
        time.sleep(0.1)  # Wait a bit to ensure the command is processed
        self.timer.start(self.updateTimeInterval)  # Restart the timer with the original interval

    def setAllSweepTargets(self):
        self.timer.stop()
        self.enableSignals = False  # Disable signals-slots during sweep selection
        if self.chkAll.styleSheet() == "":
            self.chkAll.setStyleSheet("background-color: green")
            self.chkAll.setText("Disable All")
            for i in range(NTARGET):
                self.target_chkBox[i].setChecked(True)
            tempMask = (1 << 16) - 1  # Set all bits to 1
            self.controller.setSweepMask(tempMask)
        elif self.chkAll.styleSheet() == "background-color: green":
            print("Uncheck all targets from sweep.")
            self.chkAll.setStyleSheet("")
            self.chkAll.setText("Eanble All")
            for i in range(NTARGET):
                self.target_chkBox[i].setChecked(False)
            self.controller.setSweepMask(0)
        self.enableSignals = True  # Enable signals-slots after sweep selection 
        time.sleep(0.1)  # Wait a bit to ensure the command is processed
        self.timer.start(self.updateTimeInterval)  # Restart the timer with the original interval


    def LockPosition(self):
        if self.controller.connected:

            if self.bnLockPos.styleSheet() == "":
                self.bnLockPos.setStyleSheet("background-color: green")
                
                self.controller.startQX4LockPosition()
                self.isQX4Locking = True

                time.sleep(0.5)  # Wait a bit to ensure the command is processed
                self.UpdateQX4ParametersFromMemory()

                self.SetEnableGeneralControl(False)
                self.setEnableSpinControl(False)
                self.setEnableSweepControl(False)

            else:

                self.controller.stopQX4LockPosition()
                self.isQX4Locking = False
            
                self.bnLockPos.setStyleSheet("")
                self.UpdateQX4ParametersFromMemory()

                self.SetEnableGeneralControl(True)
                self.setEnableSpinControl(True)
                self.setEnableSweepControl(True)

    #======================================================================================== Sweep Control
    def SetMaxSweepSpeed(self):
        #cal the maximum speed allowed
        maxSpeed1 = 60. / 0.0536 * (1 - self.spSpokeWidth.value() / 512)  
        maxSpeed2 = 60. / 0.0044 * (self.spSpokeWidth.value() / 512)
        maxSpeed = min(maxSpeed1, maxSpeed2)

        # Make maxSpeed divisible by 0.25
        maxSpeed = math.floor(maxSpeed / 0.25) * 0.25
        self.spSweepSpeed.setMaximum(maxSpeed)
        print(f"Spoke Width set to {self.spSpokeWidth.value():.0f}, max sweep speed: {maxSpeed:.2f} rpm")


    def SetSpokeWidth(self):
        if self.enableSignals:
            self.controller.setSpokeWidth(self.spSpokeWidth.value())
            self.SetMaxSweepSpeed()

    def SetSpokeOffset(self):
        if self.enableSignals:
            self.controller.setSpokeOffset(self.spSpokeWidth.value())

    def SetSweepSpeed(self):
        if self.enableSignals:
            self.controller.setSweepSpeed( self.spSweepSpeed.value())
            self.statusSweepSpeed.setText(f"{self.spSweepSpeed.value()/60.:.1f}")

    def SetSweepCutOff(self):
        if self.enableSignals:
            self.controller.setSweepCutOff(self.spSweepCutOff.value())

    def StartSweep(self):
        if self.controller.connected:
            self.SetEnableGeneralControl(False)
            self.setEnableSpinControl(False)
            self.setEnableSweepControl(False, True)
            self.setEnableTargetControl(False)

            # if self.cbSweepDirection.currentIndex() == 0:
            #     print("Starting sweep and spin in clockwise direction.")
            #     self.controller.send_message("DI100")
            # else:
            #     print("Starting sweep and spin in counterclockwise direction.")
            #     self.controller.send_message("DI-100")

            self.controller.send_message("DI100")
            self.controller.startSpinSweep()
        
            self.updateTimeInterval = 300 
            self.timer.stop()
            self.timer.start(self.updateTimeInterval)

    def StopSweep(self):
        if self.controller.connected:
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
                    
                if status  == 7:  # 00000111 in decimal
                    self.controller.isSpinning = False
                    break

                if new_velocity > 1 and abs(new_velocity - old_velocity) < 0.1:
                    print("Velocity not changing, forcing stop.")
                    break

                time.sleep(0.3)
                QApplication.processEvents()  # Process events to update the UI

            self.controller.send_message("SK") 
            self.controller.send_message('IO7')
            self.controller.send_message('RLO0') 

            self.direction_label.setStyleSheet("color: blue;")
            self.direction_label.setText("Only Positive Direction")

            self.Update_Status()

            self.SetEnableGeneralControl(True)
            self.setEnableSpinControl(True)
            self.setEnableSweepControl(True, True)
            self.setEnableTargetControl(True)

            for i in range(NTARGET):
                self.target_buttons[i].setEnabled(True)
                self.target_pos[i].setEnabled(True)

            self.updateTimeInterval = DAEFUL_POS_UPDATE_INTERVAL 
            self.timer.stop()
            self.timer.start(self.updateTimeInterval)

            self.UpdateButtonsColor()



    #======================================================================================== Spin Control
    def SetSpinSpeed(self):
        if self.enableSignals:
            speed = self.spSpinSpeed.value()
            self.controller.setJogSpeed(speed)
            self.statusSpinSpeed.setText(f"{speed*60:.1f}")
            print(f"Spin Speed set to {speed:.2f} [r/s] = {speed*60:.1f} [rpm]")

    def SetSpinAccel(self):
        if self.enableSignals:
            accel = self.spSpinAccel.value()
            self.controller.setJogAccel(accel)
            print(f"Spin Acceleration set to {accel:.3f} [r/s^2]")

    def StartSpin(self):
        if self.controller.connected:

            self.SetEnableGeneralControl(False)
            self.setEnableSpinControl(False, True)
            self.setEnableSweepControl(False)
            self.setEnableTargetControl(False)

            QApplication.focusWidget().clearFocus()

            self.updateTimeInterval = 300 
            self.timer.stop()
            self.timer.start(self.updateTimeInterval)  # Restart the timer with the new interval

            if self.cbDirection.currentIndex() == 0:
               print("Starting spin in clockwise direction.")
               self.controller.send_message("DI100")   
            else:
                print("Starting spin in counterclockwise direction.")
                self.controller.send_message("DI-100")

            self.controller.send_message("DI100")   # ALWSY POSITIVE NUMBER
            self.controller.startSpin()

            self.pauseUpdate = False

    def StopSpin(self):
        if self.controller.connected:

            self.controller.stopSpin()
            QApplication.focusWidget().clearFocus()

            self.pauseUpdate = False

            self.updateTimeInterval = 5000 
            self.timer.stop()
            self.timer.start(self.updateTimeInterval)  # Restart the timer with the new interval

            self.SetEnableGeneralControl(True)
            self.setEnableSpinControl(True, True)
            self.setEnableSweepControl(True)
            self.setEnableTargetControl(True)

            self.UpdateButtonsColor()

    #======================================================================================== QX4 Control
    def SetQX4Position(self):
        if self.enableSignals:
            pos = int(self.qx4SetPos.text())
            self.controller.setQX4EncoderDemandPos(pos)

    def SetQX4UpdateInterval(self):
        if self.enableSignals:
            interval = int(self.qx4UpdateInterval.text())
            self.controller.setQX4ControUpdate(interval)

    def SetQX4SlewSpeed(self):
        if self.enableSignals:
            speed = int(self.qx4SlewSpeed.text())
            self.controller.setQX4SlewSpeed(speed)

    def SetQX4ServoSpeed(self):
        if self.enableSignals:
            speed = int(self.qx4ServoSpeed.text())
            self.controller.setQX4ServoSlewSpeed(speed)

    #======================================================================================== Load/Save Target Names
    def load_targets_click(self):
        self.fileName, _ = QFileDialog.getOpenFileName(self, "Open Target Names", "", "JSON Files (*.json)")
        self.load_targets_info()

    def save_targets_click(self):
        self.fileName, _ = QFileDialog.getSaveFileName(self, "Save Target Names", "", "JSON Files (*.json)")
        print(f"Save to file: |{self.fileName}|")
        if self.fileName == "" or self.fileName is None:
            print("No file name specified. Targets not saved.")
            return
        self.save_targets_info()

        self.fileNameLineEdit.setText(self.fileName)
        self.Save_program_settings()

        
    def load_targets_info(self):

        print(f"Load from file: |{self.fileName}|")

        if self.fileName is not None and self.fileName != "":
            try:
                with open(self.fileName, "r") as file:
                    data = json.load(file)
                    if isinstance(data, list):
                        for item in data:
                            idx = item.get("index")
                            name = item.get("name")
                            pos = str(item.get("position"))
                            if isinstance(idx, int) and 0 <= idx < len(self.target_buttons):
                                self.target_buttons[idx].setText(name)
                                self.target_pos[idx].setText(pos)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"Error loading targets position: {e}")
                self.fileName = None
                self.fileNameLineEdit.setText("")
                return
        else:
            self.fileName = None
            self.fileNameLineEdit.setText("")

        self.fileNameLineEdit.setText(self.fileName)

    def save_targets_info(self):
        if  self.fileName is not None and self.fileName != "":
            data = [{"index": i, "name": btn.text(), "position" : int(self.target_pos[i].text())} for i, btn in enumerate(self.target_buttons)]
            with open(self.fileName, "w") as file:
                json.dump(data, file, indent=2)

            print(f"Targets name and position saved to {self.fileName}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TargetWheelControl()
    window.show()
    sys.exit(app.exec())
