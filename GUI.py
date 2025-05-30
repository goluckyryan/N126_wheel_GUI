#!/usr/bin/env python3

import sys
import json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QGridLayout,
    QGroupBox, QLabel, QHBoxLayout, QFileDialog, QCheckBox, QLineEdit
)
from PyQt6.QtCore import Qt

NTARGET = 16

class TargetWheelControl(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Target Wheel Control")
        self.target_buttons = []
        self.target_chkBox = []
        self.target_names = [f"Target {i}" for i in range(16)]
        self.fileName = ""

        self.button_clicked_id = None

        self.init_ui()

    def init_ui(self):
        main_layout = QGridLayout()

        ########### Target group
        target_group = QGroupBox("Target")
        target_layout = QGridLayout()
        target_group.setLayout(target_layout)

        target_layout.addWidget(QLabel("Name"), 0, 1, 1, 4)
        target_layout.addWidget(QLabel("Swp."), 0, 5)

        # Target Buttons Grid
        for i in range(NTARGET):
            target_layout.addWidget(QLabel(str(i)), 1+i, 0)
            btn = QPushButton(self.target_names[i])
            btn.clicked.connect(lambda _, idx=i: self.Target_picked(idx))
            self.target_buttons.append(btn)
            target_layout.addWidget(btn, 1+i, 1, 1, 4)
            
            chkBox = QCheckBox()
            chkBox.clicked.connect(lambda _, idx=i: self.Sweep_picked(idx))
            self.target_chkBox.append(chkBox)
            target_layout.addWidget(chkBox, 1+i, 5)


        # Load/Save Buttons
        load_button = QPushButton("Load Targets")
        save_button = QPushButton("Save Targets")
        load_button.clicked.connect(self.load_targets)
        save_button.clicked.connect(self.save_targets)
        target_layout.addWidget(load_button, NTARGET + 2, 1, 1, 2)
        target_layout.addWidget(save_button, NTARGET + 2, 3, 1, 2)

        self.fileNameLineEdit = QLineEdit("")
        self.fileNameLineEdit.setReadOnly(True)
        target_layout.addWidget(self.fileNameLineEdit, NTARGET + 3, 1, 1, 4)
        

        main_layout.addWidget(target_group, 0, 0, 3, 1)

        ########### Status Group
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()
        status_group.setLayout(status_layout)
        self.status_label = QLabel("Idle")
        status_layout.addWidget(self.status_label)
        main_layout.addWidget(status_group, 0, 1)

        ########### Spinning Control Group
        spin_group = QGroupBox("Spinning Control")
        spin_layout = QVBoxLayout()
        spin_group.setLayout(spin_layout)
        self.spin_label = QLabel("Spin Speed: N/A")
        spin_layout.addWidget(self.spin_label)
        main_layout.addWidget(spin_group, 1, 1)

        ########### Sweeper Control Group
        sweep_group = QGroupBox("Sweeper Control")
        sweep_layout = QVBoxLayout()
        sweep_group.setLayout(sweep_layout)
        self.sweep_label = QLabel("Sweep Mode: OFF")
        sweep_layout.addWidget(self.sweep_label)
        main_layout.addWidget(sweep_group, 2, 1)

        self.setLayout(main_layout)


    def Target_picked(self, id):
        print(f"Target : {self.target_names[id]}, id : {id}")
        self.target_buttons[id].setStyleSheet("background-color: green")

        if self.button_clicked_id != None:
            self.target_buttons[self.button_clicked_id].setStyleSheet("")

        self.button_clicked_id = id



    def Sweep_picked(self, id):
        print(f"Sweep Target : {self.target_names[id]}, id : {id}")


    def load_targets(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open Target Names", "", "JSON Files (*.json)")
        if filename:
            with open(filename, "r") as file:
                data = json.load(file)
                if isinstance(data, list):
                    for item in data:
                        idx = item.get("index")
                        name = item.get("name")
                        if isinstance(idx, int) and 0 <= idx < len(self.target_buttons):
                            self.target_buttons[idx].setText(name)

        self.fileNameLineEdit.setText(filename)

    def save_targets(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Target Names", "", "JSON Files (*.json)")
        if filename:
            data = [{"index": i, "name": btn.text()} for i, btn in enumerate(self.target_buttons)]
            with open(filename, "w") as file:
                json.dump(data, file, indent=2)

        self.fileNameLineEdit.setText(filename)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TargetWheelControl()
    window.show()
    sys.exit(app.exec())
