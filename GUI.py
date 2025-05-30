#!/usr/bin/env python3

import sys
import json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QGridLayout,
    QGroupBox, QLabel, QHBoxLayout, QFileDialog, QCheckBox, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer

from Library import Controller

NTARGET = 16

class TargetWheelControl(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Target Wheel Control")
        self.target_buttons = []
        self.target_chkBox = []
        self.target_pos = []
        self.target_names = [f"Target {i}" for i in range(16)]
        self.fileName = ""

        self.button_clicked_id = None

        self.controller = Controller()
        self.leIP = QLineEdit()
        self.lePort = QLineEdit()
        self.bnConnect = QPushButton("Connect")
        self.bnConnect.clicked.connect(self.Connect_Server)

        self.connectionStatus = QLabel("Not Connect.")
        self.connectionStatus.setStyleSheet("color : red")

        self.init_ui()

        self.Load_program_setting()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.Update_Status)
        self.timer.start(1000) # 1 sec

    def __del__(self):
        print("============= Program Ended.")

    def init_ui(self):
        main_layout = QGridLayout()

        ########### Server 
        server_group = QGroupBox("Server")
        server_layout = QGridLayout()
        server_group.setLayout(server_layout)

        server_layout.addWidget(QLabel("IP :"), 0, 0)
        server_layout.addWidget(self.leIP, 0, 1, 1, 5)
        server_layout.addWidget(QLabel("Port :"), 1, 0)
        server_layout.addWidget(self.lePort, 1, 1, 1, 3)
        server_layout.addWidget(self.bnConnect, 1, 4, 1, 2)

        main_layout.addWidget(server_group, 0, 0, 1, 4)

        ########### Target group
        target_group = QGroupBox("Target")
        target_layout = QGridLayout()
        target_group.setLayout(target_layout)

        target_layout.addWidget(QLabel("Name"), 0, 1, 1, 4)
        target_layout.addWidget(QLabel("Position"), 0, 5,1, 2)
        target_layout.addWidget(QLabel("Swp."), 0, 7)

        # Target Buttons Grid
        for i in range(NTARGET):
            target_layout.addWidget(QLabel(str(i)), 1+i, 0)
            
            btn = QPushButton(self.target_names[i])
            btn.clicked.connect(lambda _, idx=i: self.Target_picked(idx))
            self.target_buttons.append(btn)
            target_layout.addWidget(btn, 1+i, 1, 1, 4)

            le = QLineEdit(str(int(8192/NTARGET)*i))
            le.returnPressed.connect(lambda _, idx=i: self.SetPosition(idx))
            self.target_pos.append(le)
            target_layout.addWidget(le, 1+i, 5, 1, 2)
            
            chkBox = QCheckBox()
            chkBox.clicked.connect(lambda _, idx=i: self.Sweep_picked(idx))
            self.target_chkBox.append(chkBox)
            target_layout.addWidget(chkBox, 1+i, 7)


        # Load/Save Buttons
        load_button = QPushButton("Load Targets")
        save_button = QPushButton("Save Targets")
        load_button.clicked.connect(self.load_targets_click)
        save_button.clicked.connect(self.save_targets)
        target_layout.addWidget(load_button, NTARGET + 2, 1, 1, 2)
        target_layout.addWidget(save_button, NTARGET + 2, 3, 1, 2)

        self.fileNameLineEdit = QLineEdit("")
        self.fileNameLineEdit.setReadOnly(True)
        target_layout.addWidget(self.fileNameLineEdit, NTARGET + 3, 1, 1, 4)
        

        main_layout.addWidget(target_group, 1, 0, 3, 2)

        ########### Status Group
        status_group = QGroupBox("Status")
        status_layout = QGridLayout()
        status_group.setLayout(status_layout)

        row = 0
        status_layout.addWidget(self.connectionStatus, row, 0, 1, 3)

        row += 1
        status_layout.addWidget(QLabel("Encoder Pos : "), row, 0)
        self.Encoderpos = QLineEdit()
        self.Encoderpos.setReadOnly(True)
        status_layout.addWidget(self.Encoderpos, row, 1, 1, 2)

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
 
        main_layout.addWidget(status_group, 1, 2, 1, 1)

        ########### Spinning Control Group
        spin_group = QGroupBox("Spinning Control")
        spin_layout = QVBoxLayout()
        spin_group.setLayout(spin_layout)

        self.spin_label = QLabel("Spin Speed: N/A")
        spin_layout.addWidget(self.spin_label)
        
        bnSpinStart = QPushButton("Start Spin")
        spin_layout.addWidget(bnSpinStart)
        bnSpinStart.clicked.connect(lambda: self.controller.send_message("CJ"))
        bnSpinStop = QPushButton("Stop Spin")
        spin_layout.addWidget(bnSpinStop)
        bnSpinStop.clicked.connect(lambda: self.controller.send_message("SJ"))
        
        main_layout.addWidget(spin_group, 2, 2, 1, 1)

        ########### Sweeper Control Group
        sweep_group = QGroupBox("Sweeper Control")
        sweep_layout = QVBoxLayout()
        sweep_group.setLayout(sweep_layout)
        self.sweep_label = QLabel("Sweep Mode: OFF")
        sweep_layout.addWidget(self.sweep_label)
        main_layout.addWidget(sweep_group, 3, 2, 1, 1)

        self.setLayout(main_layout)

    def Load_program_setting(self):
        with open("programSettings.json", "r") as file:
            data = json.load(file)[0]
            self.leIP.setText(data["IP"])
            self.lePort.setText(str(data["Port"]))
            self.Connect_Server()

            self.fileName = data["target_file"]
            self.fileNameLineEdit.setText(self.fileName)
            self.load_targets()

    def Save_program_settings(self):
        pass

    def Connect_Server(self):
        self.controller.Connect(self.leIP.text(), int(self.lePort.text()))
        if self.controller.connected:
            self.connectionStatus.setText("Connected.")
            self.connectionStatus.setStyleSheet("color : blue")
        else:
            self.connectionStatus.setText("Not Connect.")
            self.connectionStatus.setStyleSheet("color : red")

    def Update_Status(self):
        self.Encoderpos.setText(self.controller.query("RUe1"))

    def Send_Message(self):
        self.leGetMsg.setText(self.controller.query(self.leSendMsg.text()))

    def Target_picked(self, id):
        print(f"Target : {self.target_names[id]}, id : {id}")
        self.target_buttons[id].setStyleSheet("background-color: green")

        if self.button_clicked_id != None:
            self.target_buttons[self.button_clicked_id].setStyleSheet("")

        self.button_clicked_id = id

    def SetPosition(self, id):
        pass

    def Sweep_picked(self, id):
        print(f"Sweep Target : {self.target_names[id]}, id : {id}")

    def load_targets_click(self):
        self.fileName, _ = QFileDialog.getOpenFileName(self, "Open Target Names", "", "JSON Files (*.json)")
        self.load_targets()
        
    def load_targets(self):
        if self.fileName:
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


        self.fileNameLineEdit.setText(self.fileName)

    def save_targets(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Target Names", "", "JSON Files (*.json)")
        if filename:
            data = [{"index": i, "name": btn.text(), "position" : int(self.target_pos[i].text())} for i, btn in enumerate(self.target_buttons)]
            with open(filename, "w") as file:
                json.dump(data, file, indent=2)

        self.fileNameLineEdit.setText(filename)
        self.fileName = filename

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TargetWheelControl()
    window.show()
    sys.exit(app.exec())
