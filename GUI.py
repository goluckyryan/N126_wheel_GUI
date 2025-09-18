#!/usr/bin/env python3

import sys
import json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QGridLayout,
    QGroupBox, QLabel,  QFileDialog, QCheckBox, QLineEdit, QDoubleSpinBox,
    QApplication, QComboBox, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent
import time

from Library import Controller, STEP_PER_REVOLUTION

NTARGET = 16
DAEFUL_POS_UPDATE_INTERVAL = 2000  # milliseconds


class CustomButton(QPushButton):
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


#####################################################################
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

        self.button_clicked_id = None

        self.controller = Controller()
        self.leIP = QLineEdit()
        self.lePort = QLineEdit()
        self.bnConnect = QPushButton("Connect / Refresh")
        self.bnConnect.clicked.connect(self.Connect_Server)

        # self.connectionStatus = QLabel("Not Connect.")
        # self.connectionStatus.setStyleSheet("color : red")

        self.init_ui()

        self.Load_program_setting()
        self.Connect_Server()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.Update_Position)
        self.updateTimeInterval = DAEFUL_POS_UPDATE_INTERVAL  # milliseconds
        self.timer.start(self.updateTimeInterval) 
        self.pauseUpdate = False

    def closeEvent(self, event: QCloseEvent):
        if self.fileName is None or self.fileName == "":
            self.save_targets_click()
        else:
            self.save_targets_info()
        self.Save_program_settings()
        self.controller.stopSpin()
        self.controller.stopSpinSweep()
        self.controller.disconnect()
        event.accept()  # Optional: confirm you want to close
        print("============= Program Ended.")

    def init_ui(self):
        main_layout = QGridLayout()

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
            
            btn = CustomButton(self.target_names[i])
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

        # Load/Save Buttons
        row += 1
        load_button = QPushButton("Load Targets")
        save_button = QPushButton("Save Targets")
        load_button.clicked.connect(self.load_targets_click)
        save_button.clicked.connect(self.save_targets_click)
        target_layout.addWidget(load_button, row, 1, 1, 2)
        target_layout.addWidget(save_button, row, 3, 1, 2)

        row += 1
        self.fileNameLineEdit = QLineEdit("")
        self.fileNameLineEdit.setReadOnly(True)
        target_layout.addWidget(self.fileNameLineEdit, row, 1, 1, 9)
        

        ########### Server 
        server_group = QGroupBox("Server")
        server_layout = QGridLayout()
        server_group.setLayout(server_layout)

        server_layout.addWidget(QLabel("IP :"), 0, 0)
        server_layout.addWidget(self.leIP, 0, 1, 1, 5)
        server_layout.addWidget(QLabel("Port :"), 1, 0)
        server_layout.addWidget(self.lePort, 1, 1, 1, 3)
        server_layout.addWidget(self.bnConnect, 1, 4, 1, 2)


        ########### Status Group
        status_group = QGroupBox("General Control")
        status_layout = QGridLayout()
        status_group.setLayout(status_layout)

        # row = 0
        # status_layout.addWidget(self.connectionStatus, row, 0, 1, 3)

        row = 0
        status_layout.addWidget(QLabel("Encoder Pos. : "), row, 0)
        self.EncoderPos = QLineEdit()
        self.EncoderPos.setReadOnly(True)
        status_layout.addWidget(self.EncoderPos, row, 1, 1, 2)

        row += 1
        status_layout.addWidget(QLabel("Encoder mod Pos. : "), row, 0)
        self.EncoderModPos = QLineEdit()
        self.EncoderModPos.setReadOnly(True)
        status_layout.addWidget(self.EncoderModPos, row, 1, 1, 2)

        row += 1
        status_layout.addWidget(QLabel("Encoder Rev. : "), row, 0)
        self.EncoderRev = QLineEdit()
        self.EncoderRev.setReadOnly(True)
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
        status_layout.addWidget(QLabel("Deaccel. [r/s^2] : "), row, 0)
        self.spDeccel = QDoubleSpinBox()
        self.spDeccel.setDecimals(3)
        self.spDeccel.setSingleStep(0.001)
        self.spDeccel.setRange(0.167, 1000.0)
        self.spDeccel.valueChanged.connect(self.SetDeaccel)
        status_layout.addWidget(self.spDeccel, row, 1, 1, 2)

        row += 1
        status_layout.addWidget(QLabel("Move Distance : "), row, 0)
        self.spMoveDistance = QDoubleSpinBox()
        self.spMoveDistance.setDecimals(0)
        self.spMoveDistance.setSingleStep(1)
        self.spMoveDistance.setRange(-100000, 100000)
        self.spMoveDistance.valueChanged.connect(self.SetMoveDistance)
        status_layout.addWidget(self.spMoveDistance, row, 1, 1, 2)

        row += 1
        self.bnMove = QPushButton("Move")
        status_layout.addWidget(self.bnMove, row, 0, 1, 3)
        self.bnMove.clicked.connect(self.moveDistance)

        row += 1
        bnSeekHome = QPushButton("Seek Home")
        status_layout.addWidget(bnSeekHome, row, 0, 1, 3)
        bnSeekHome.clicked.connect(self.SeekHome)

        row += 1
        bnZeroEncoderPosition = QPushButton("Zero Encoder Position")
        status_layout.addWidget(bnZeroEncoderPosition, row, 0, 1, 3)
        bnZeroEncoderPosition.clicked.connect(self.ZeroEncoderPosition)

        row += 1
        self.leSendMsg = QLineEdit()
        self.leSendMsg.returnPressed.connect(self.Send_Message)
        status_layout.addWidget(QLabel("Send CMD : "), row, 0)
        status_layout.addWidget(self.leSendMsg, row, 1, 1, 2)

        row += 1
        self.leGetMsg = QLineEdit()
        self.leGetMsg.setReadOnly(True)
        status_layout.addWidget(QLabel("Reply : "), row, 0)
        status_layout.addWidget(self.leGetMsg, row, 1, 1, 2)

        row += 1
        bnUpdateState = QPushButton("Update Status")
        bnUpdateState.clicked.connect(self.Update_Status)
        status_layout.addWidget(bnUpdateState, row, 0, 1, 3)

        # row += 1
        # bnReset = QPushButton("Reset")
        # bnReset.clicked.connect(lambda: self.controller.reset())
        # status_layout.addWidget(bnReset, row, 0, 1, 3)

        ########### Lock Pos. Group
        self.lock_group = QGroupBox("Lock Position")
        lock_layout = QGridLayout()
        self.lock_group.setLayout(lock_layout)

        row = 0
        self.bnLockPos = QPushButton("Lock Position")
        lock_layout.addWidget(self.bnLockPos, row, 0, 1, 3)
        self.bnLockPos.clicked.connect(self.LockPosition)

        row += 1
        self.cbbLLockPos = QComboBox()
        self.cbbLLockPos.addItems([f"{self.target_names[i]}" for i in range(NTARGET)])
        self.cbbLLockPos.addItems(["Manual Position"])
        lock_layout.addWidget(self.cbbLLockPos, row, 0, 1, 3)
        self.cbbLLockPos.currentIndexChanged.connect(self.LockPositionChanged)

        row += 1
        lock_layout.addWidget(QLabel("Manual Pos. : "), row, 0, 1, 1)
        self.leLockPos = QLineEdit("0")
        self.leLockPos.setEnabled(False)
        lock_layout.addWidget(self.leLockPos, row, 1, 1, 2)


        ########### Spinning Control Group
        self.spin_group = QGroupBox("Spinning Control")
        spin_layout = QGridLayout()
        self.spin_group.setLayout(spin_layout)

        row = 0
        self.spSpinSpeed = QDoubleSpinBox()
        self.spSpinSpeed.setDecimals(2)
        self.spSpinSpeed.setSingleStep(0.1)
        self.spSpinSpeed.setRange(0.0042, 80.0)
        spin_layout.addWidget(QLabel("Spin Speed [r/s] : "), row, 0)
        spin_layout.addWidget(self.spSpinSpeed, row, 1, 1, 2)
        self.spSpinSpeed.valueChanged.connect(self.SetSpinSpeed)

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

 
        ########### Sweeper Control Group
        sweep_group = QGroupBox("Veto Sweeper Control")
        sweep_layout = QGridLayout()
        sweep_group.setLayout(sweep_layout)

        row = 0
        self.spSweepWidth = QDoubleSpinBox()
        self.spSweepWidth.setDecimals(0)
        self.spSweepWidth.setSingleStep(1)
        self.spSweepWidth.setRange(0, 512)
        self.spSweepWidth.valueChanged.connect(self.SetSweepWidth)
        sweep_layout.addWidget(QLabel("Spoke Width : "), row, 0)
        sweep_layout.addWidget(self.spSweepWidth, row, 1, 1, 1)

        row += 1
        self.spSpokeWidth = QDoubleSpinBox()
        self.spSpokeWidth.setDecimals(0)
        self.spSpokeWidth.setSingleStep(1)
        self.spSpokeWidth.setRange(0, 511)
        self.spSpokeWidth.valueChanged.connect(self.SetSpokeWidth)
        sweep_layout.addWidget(QLabel("Spoke offset : "), row, 0)
        sweep_layout.addWidget(self.spSpokeWidth, row, 1, 1, 1)
 
        row += 1
        self.spSweepSpeed = QDoubleSpinBox()
        self.spSweepSpeed.setDecimals(2)
        self.spSweepSpeed.setSingleStep(0.25)
        self.spSweepSpeed.setRange(0, 1300)
        self.spSweepSpeed.valueChanged.connect(self.SetSweepSpeed)
        sweep_layout.addWidget(QLabel("Speed [rpm] : "), row, 0)
        sweep_layout.addWidget(self.spSweepSpeed, row, 1, 1, 1)
 
        row += 1
        self.spSweepCutOff = QDoubleSpinBox()
        self.spSweepCutOff.setDecimals(2)
        self.spSweepCutOff.setSingleStep(0.25)
        self.spSweepCutOff.setRange(0, 1300)
        self.spSweepCutOff.valueChanged.connect(self.SetSweepCutOff)
        sweep_layout.addWidget(QLabel("Cut Off [rpm] : "), row, 0)
        sweep_layout.addWidget(self.spSweepCutOff, row, 1, 1, 1)

        row += 1
        self.cbSweepDirection = QComboBox()
        self.cbSweepDirection.addItems(["Clockwise (+)", "Counterclockwise (-)"])
        sweep_layout.addWidget(QLabel("Direction : "), row, 0)
        sweep_layout.addWidget(self.cbSweepDirection, row, 1, 1, 1)
 
        row += 1
        self.sweepStart = QPushButton("Start sweep and spin")
        self.sweepStart.clicked.connect(self.StartSweep)
        sweep_layout.addWidget(self.sweepStart, row, 0, 1, 2)

        row += 1
        self.sweepStop = QPushButton("Stop sweep and spin")
        self.sweepStop.setEnabled(False)
        self.sweepStop.clicked.connect(self.StopSweep)
        sweep_layout.addWidget(self.sweepStop, row, 0, 1, 2)


        # Add groups to main layout
        main_layout.addWidget(     target_group, 0, 0, 5, 2)
        main_layout.addWidget(     server_group, 0, 2, 1, 2)
        main_layout.addWidget(     status_group, 1, 2, 3, 1)
        main_layout.addWidget(  self.lock_group, 4, 2, 1, 1)      
        main_layout.addWidget(  self.spin_group, 1, 3, 2, 1)
        main_layout.addWidget(      sweep_group, 3, 3, 2, 1)

        self.setLayout(main_layout)


    #########################################################
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

    def UpdateButtonsColor(self, tolerance=0.01):
        current_Angle = self.controller.position % STEP_PER_REVOLUTION / STEP_PER_REVOLUTION
        for i, pos in enumerate(self.target_pos):
            target_Angle = int(pos.text()) % STEP_PER_REVOLUTION / STEP_PER_REVOLUTION
            if abs(current_Angle - target_Angle) < tolerance:
                if self.button_clicked_id != i:
                    self.target_buttons[i].setStyleSheet("background-color: green")
                    if self.button_clicked_id is not None:
                        self.target_buttons[self.button_clicked_id].setStyleSheet("")
                    self.button_clicked_id = i
                break

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
            self.spMoveDistance.setValue(self.controller.moveDistance)

            self.spSpinSpeed.setValue(self.controller.jogSpeed)
            self.spSpinAccel.setValue(self.controller.jogAccel)
            if self.controller.moveDistance >= 0 :
                self.cbDirection.setCurrentIndex(0)  # Clockwise
            else:
                self.cbDirection.setCurrentIndex(1)

            self.spSpinAccel.setStyleSheet("")

            #=== check current position and set the corresponding 
            self.UpdateButtonsColor()

            #==== sweep parameters
            self.spSweepWidth.setValue(self.controller.spokeOffset)
            self.spSpokeWidth.setValue(self.controller.spokeWidth)
            self.spSweepSpeed.setValue(self.controller.sweepSpeed/4)
            self.spSweepCutOff.setValue(self.controller.sweepCutOff/4)

            #=== sweep mask
            for i in range(NTARGET):
                bitPos = 15 - i
                if self.controller.sweepMask & (1 << bitPos):
                    self.target_chkBox[i].setChecked(True)
            if self.controller.sweepMask == (1 << 16) - 1:
                self.chkAll.setStyleSheet("background-color: green")
                self.chkAll.setText("Disable All")
            

    def Update_Position(self): # see self.updateTimeInterval
        if self.pauseUpdate == False:
            self.controller.getPosition(False) 
            self.EncoderPos.setText(f"{self.controller.position}") 
            self.EncoderModPos.setText(f"{self.controller.position%STEP_PER_REVOLUTION:.0f}")
            self.EncoderRev.setText(f"{self.controller.position/STEP_PER_REVOLUTION:.2f} [rev]")

    def SetAccel(self):
        if self.enableSignals:
            accel = self.spAccel.value()
            self.controller.setAccelRate(accel)
            print(f"Acceleration set to {accel:.3f} [r/s^2]")
    
    def SetSpeed(self):
        if self.enableSignals:
            speed = self.spSpeed.value()
            self.controller.setVelocity(speed)
            print(f"Speed set to {speed:.1f} [r/s]")

    def SetDeaccel(self):
        if self.enableSignals:
            deaccel = self.spDeccel.value()
            self.controller.setDeaccelRate(deaccel)
            print(f"Deacceleration set to {deaccel:.3f} [r/s^2]")

    def SetMoveDistance(self):
        if self.enableSignals:
            distance = self.spMoveDistance.value()
            self.controller.setMoveDistance(distance)
            print(f"Move Distance set to {distance:.0f} [steps]")

    def moveDistance(self):
        if self.controller.connected:
            distance = self.spMoveDistance.value()
            if distance != 0:
                print(f"Moving {distance:.0f} steps.")
                self.controller.send_message("FL")

                self.CheckPostionStable()  # Check if the position is stable after moving

    def Send_Message(self):
        self.timer.stop()  # Stop the timer to prevent updates during message sending
        self.leGetMsg.setText(self.controller.send_message(self.leSendMsg.text()))
        self.leSendMsg.selectAll()
        time.sleep(0.1)  # Wait a bit to ensure the command is processed
        self.timer.start(self.updateTimeInterval)  # Restart the timer with the original interval

    def Target_picked(self, id):
        if self.target_buttons[id].isChangeNameMode:
            self.target_names[id] = self.target_buttons[id].name
            print(f"Change Target Name: {self.target_names[id]}, id : {id}")
            QApplication.processEvents()  # Process events to update the UI
            return

        #=== change color
        if  self.button_clicked_id != id:
            self.target_buttons[id].setStyleSheet("background-color: green")
            if self.button_clicked_id != None:
                self.target_buttons[self.button_clicked_id].setStyleSheet("")

            self.button_clicked_id = id

        # === move to target position
        target_position = int(self.target_pos[id].text())
        print(f"Target : {self.target_names[id]}, id : {id}, position : {target_position}")

        tarAngle = (target_position % STEP_PER_REVOLUTION ) / STEP_PER_REVOLUTION
        posAngle = (self.controller.position % STEP_PER_REVOLUTION ) / STEP_PER_REVOLUTION
        diffAngle = tarAngle - posAngle
        if diffAngle < -0.5:
            diffAngle += 1.0
        elif diffAngle > 0.5:
            diffAngle -= 1.0
        print(f"Target Angle : {tarAngle:.4f}, Current Angle : {posAngle:.4f}, Difference : {diffAngle:.4f} rev.")

        moveDistance = int(diffAngle * STEP_PER_REVOLUTION)  # Convert to steps
        goto_position = self.controller.position + moveDistance 
        print(f"Moving to target position: {goto_position} mod {STEP_PER_REVOLUTION} = {goto_position % STEP_PER_REVOLUTION} = {target_position}.")

        self.message.setText(f"Moving to absolute position: {goto_position}.")

        self.controller.setMoveDistance(moveDistance)
        self.spMoveDistance.setValue(moveDistance)
        self.controller.send_message("FL")  # Send the command to move

        self.CheckPostionStable() 

    def SetPosition(self, id):
        # print(f"Set Position for Target {id}: {self.target_pos[id].text()}")
        self.target_rev[id].setText(str(int(self.target_pos[id].text()) / STEP_PER_REVOLUTION))

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


    def SetSweepWidth(self):
        if self.enableSignals:
            self.controller.setSpokeOffset(self.spSweepWidth.value())
    def SetSpokeWidth(self):
        if self.enableSignals:
            self.controller.setSpokeWidth(self.spSpokeWidth.value())
    def SetSweepSpeed(self):
        if self.enableSignals:
            haha = int(self.spSweepSpeed.value() * 4)
            self.spSweepSpeed.setValue(haha/4)
            self.controller.setSweepSpeed(haha)
    def SetSweepCutOff(self):
        if self.enableSignals:
            haha = int(self.spSweepCutOff.value() * 4)
            self.spSweepCutOff.setValue(haha/4)
            self.controller.setSweepCutOff(haha)

    def StartSweep(self):
        if self.controller.connected:
            self.sweepStart.setEnabled(False)
            self.sweepStop.setEnabled(True)

            for i in range(NTARGET):
                self.target_buttons[i].setEnabled(False)
                self.target_buttons[i].setStyleSheet("background-color: lightgray")
                self.target_pos[i].setEnabled(False)

            self.spin_group.setEnabled(False)
            self.spSweepSpeed.setEnabled(False)

            if self.cbSweepDirection.currentIndex() == 0:
                print("Starting sweep and spin in clockwise direction.")
                self.controller.send_message("DI100")
            else:
                print("Starting sweep and spin in counterclockwise direction.")
                self.controller.send_message("DI-100")

            self.controller.startSpinSweep()
        
            self.updateTimeInterval = 500 
            self.timer.stop()
            self.timer.start(self.updateTimeInterval)


    def StopSweep(self):
        if self.controller.connected:
            self.sweepStart.setEnabled(True)
            self.sweepStop.setEnabled(False)

            for i in range(NTARGET):
                self.target_buttons[i].setEnabled(True)
                self.target_buttons[i].setStyleSheet("")
                self.target_pos[i].setEnabled(True)

            self.spin_group.setEnabled(True)
            self.spSweepSpeed.setEnabled(True)

            self.controller.stopSpinSweep()

            self.updateTimeInterval = DAEFUL_POS_UPDATE_INTERVAL 
            self.timer.stop()
            self.timer.start(self.updateTimeInterval)

            self.UpdateButtonsColor()

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
            self.controller.seekHome()
            self.CheckPostionStable()
            

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

    def SetSpinSpeed(self):
        if self.enableSignals:
            speed = self.spSpinSpeed.value()
            self.controller.setJogSpeed(speed)
            print(f"Spin Speed set to {speed:.2f} [r/s]")

    def SetSpinAccel(self):
        if self.enableSignals:
            accel = self.spSpinAccel.value()
            self.controller.setJogAccel(accel)
            print(f"Spin Acceleration set to {accel:.3f} [r/s^2]")

    def StartSpin(self):
        if self.controller.connected:
            self.bnSpinStart.setEnabled(False)
            self.spSpinSpeed.setEnabled(False)
            self.spSpinAccel.setEnabled(False)
            self.cbDirection.setEnabled(False)
            self.bnSpinStop.setEnabled(True)

            for i in range(NTARGET):
                self.target_buttons[i].setEnabled(False)
                self.target_buttons[i].setStyleSheet("background-color: lightgray")
                self.target_pos[i].setEnabled(False)

            self.updateTimeInterval = 300 
            self.timer.stop()
            self.timer.start(self.updateTimeInterval)  # Restart the timer with the new interval

            if self.cbDirection.currentIndex() == 0:
                print("Starting spin in clockwise direction.")
                self.controller.send_message("DI100")
            else:
                print("Starting spin in counterclockwise direction.")
                self.controller.send_message("DI-100")
            self.controller.startSpin()

            self.pauseUpdate = False

    def StopSpin(self):
        if self.controller.connected:
            self.bnSpinStart.setEnabled(True)
            self.spSpinSpeed.setEnabled(True)
            self.spSpinAccel.setEnabled(True)
            self.cbDirection.setEnabled(True)
            self.bnSpinStop.setEnabled(False)
            self.controller.stopSpin()

            for i in range(NTARGET):
                self.target_buttons[i].setEnabled(True)
                self.target_buttons[i].setStyleSheet("")
                self.target_pos[i].setEnabled(True)

            self.pauseUpdate = False

            self.updateTimeInterval = 5000 
            self.timer.stop()
            self.timer.start(self.updateTimeInterval)  # Restart the timer with the new interval

            self.UpdateButtonsColor()

    def LockPositionChanged(self):
        if self.cbbLLockPos.currentIndex() == NTARGET:
            self.leLockPos.setEnabled(True)
        else:
            self.leLockPos.setEnabled(False)

    def LockPosition(self):
        if self.controller.connected:

            if self.bnLockPos.styleSheet() == "":

                if self.cbbLLockPos.currentIndex() == NTARGET:
                    try:
                        manual_pos = int(self.leLockPos.text())
                        print(f"Locking to manual position: {manual_pos}")
                    except ValueError:
                        print("Invalid manual position. Please enter a valid integer.")
                else:
                    target_id = self.cbbLLockPos.currentIndex()
                    target_position = int(self.target_pos[target_id].text())
                    print(f"Locking to target {self.target_names[target_id]} at position: {target_position}")

                # Send the lock command to the controller
                # use a new QThread to avoid blocking the main thread

                # set target button and position line edit to gray and disable
                for i in range(NTARGET):
                    self.target_buttons[i].setEnabled(False)
                    self.target_buttons[i].setStyleSheet("background-color: lightgray")
                    self.target_pos[i].setEnabled(False)
                    self.chkAll.setEnabled(False)
                    self.target_chkBox[i].setEnabled(False)

                self.cbbLLockPos.setEnabled(False)
                self.leLockPos.setEnabled(False)

                self.bnLockPos.setStyleSheet("background-color: green")

            else:
                print("Unlocking position.")
                # Send the unlock command to the controller

                for i in range(NTARGET):
                    self.target_buttons[i].setEnabled(True)
                    self.target_buttons[i].setStyleSheet("")
                    self.target_pos[i].setEnabled(True)
                    self.chkAll.setEnabled(True)
                    self.target_chkBox[i].setEnabled(True)

                self.cbbLLockPos.setEnabled(True)
                if self.cbbLLockPos.currentIndex() == NTARGET:
                    self.leLockPos.setEnabled(True)

                self.bnLockPos.setStyleSheet("")
                

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
