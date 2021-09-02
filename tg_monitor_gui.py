from PyQt5 import QtWidgets as Qtw
from PyQt5 import QtCore as Qtc
from PyQt5 import QtGui as Qtg
from datetime import datetime, timedelta
from bu_data_model import BU366
import sys
import socket
import time
import pandas as pd
from openpyxl.chart import ScatterChart, Reference, Series


class CheckingThread(Qtc.QThread):
    answer_thread = Qtc.pyqtSignal(str, list)
    running_state = Qtc.pyqtSignal(str)
    remaining_time = Qtc.pyqtSignal(str)
    error_threads = Qtc.pyqtSignal(str)
    running_threads = {}

    def __init__(self, threadid_, n366, total_time, polling_interval, poll_rest):
        Qtc.QThread.__init__(self)
        self.threadid = threadid_
        self.name = n366.name
        self.n366 = n366
        self.total_time = total_time
        self.polling_inteval = polling_interval
        self.poll_rest = timedelta(seconds=poll_rest)
        self.next_poll = datetime.now()
        self.end = datetime.now() + timedelta(minutes=total_time)
        self.poll_rest_flag = False
        if poll_rest > 0:
            self.poll_rest_flag = True

    def run(self):  # we run iterating over time until the test is over
        time_ = datetime.now()  # get the time now for the loop
        self.running_threads[f'{self.name}'] = self  # we add the object to the queue to be able to stop it later
        while time_ < self.end:  # main loop until end time is bigger than current time
            self.remaining_time.emit(f'{self.end - time_}')  # we update the remaining time of the test via  signal
            self.running_state.emit('°R')  # we update the status to °R via a signal
            try:  # we check if the conection is active
                self.n366.check_active()  # here we poll the DN and get the values to the dataframes
            except:  # try to reconnect
                self.running_state.emit('°RC')
                while not self.n366.connection_state and datetime.now() < self.end:  # while there is no connection we try to reconnect
                    for tu_name_disconnect in self.n366.tus:  # updates display to show the disconnection status
                        tu_item = self.n366.tus[tu_name_disconnect]
                        self.answer_thread.emit(tu_name_disconnect, [  # emit list with values
                            -1,  # set local sector
                            -100,  # set RSSI
                            0,  # set SNR
                            0,  # set RXMCS
                            0,  # set TXMCS
                            0,  # set RX PER
                            0,  # set TX PER
                            0,  # set RX MCS DR
                            0,  # set TX MCS DR
                            tu_item.get_availability(),
                            tu_item.get_disconnection_counter(),
                            tu_item.get_disconnection_ldt(),
                            tu_item.get_disconnection_lds(),
                            tu_item.get_disconnection_tdt(),
                            False,
                            0,
                        ])
                    self.n366.connect(self.n366.username, self.n366.password, 22, 1)
                # mini loop to fill in the disconnection time for each TU. We get disconnection start from object
                # and disconnection end at that time
                except_disconnection_start = self.n366.disconnection_start
                except_disconnection_end = datetime.now()
                while except_disconnection_start < except_disconnection_end:  # while there is time between both events
                    for tu_name_reconnect in self.n366.tus:  # updates display to show the disconnection status
                        except_tu_item = self.n366.tus[tu_name_reconnect]  # get each TU
                        # create a record with the disconnection parameters
                        record = {'Local Sector': 0, 'RSSI': -100, 'SNR': 0, 'MCS-RX': 0, 'MCS-TX': 0,
                                  'MCS-DR-RX': 0, 'MCS-DR-TX': 0, 'Power Index': 0}
                        record_series = pd.Series(record, name=except_disconnection_start)
                        # add the record of the disconnection
                        except_tu_item.parameters_df = except_tu_item.parameters_df.append(record_series)
                    # add the time for the next event
                    except_disconnection_start = except_disconnection_start + self.poll_rest

                continue  # jump over the loop to try to parse the active connection as we had no
                # conection extablished
            tu_counter = len(self.n366.tus)
            for tu_name in self.n366.tus:
                tu_item = self.n366.tus[tu_name]
                self.answer_thread.emit(tu_name, [  # emit list with values
                    tu_item.get_local_sector(),
                    tu_item.get_rssi(),
                    tu_item.get_snr(),
                    tu_item.get_rxmcs(),
                    tu_item.get_txmcs(),
                    tu_item.get_rxspeednum(),
                    tu_item.get_txspeednum(),
                    tu_item.get_rxmcsdr(),
                    tu_item.get_txmcsdr(),
                    tu_item.get_availability(),
                    tu_item.get_disconnection_counter(),
                    tu_item.get_disconnection_ldt(),
                    tu_item.get_disconnection_lds(),
                    tu_item.get_disconnection_tdt(),
                    tu_item.get_connection_status(),
                    tu_item.get_power_index(),
                ])
                if self.poll_rest_flag and self.next_poll < time_ and tu_counter >= 0:
                    if tu_item.connection_state:
                        record = {'Local Sector': tu_item.get_local_sector(),
                                  'RSSI': tu_item.get_rssi(), 'SNR': tu_item.get_snr(),
                                  'MCS-RX': tu_item.get_rxmcs(), 'MCS-TX': tu_item.get_txmcs(),
                                  'MCS-DR-RX': tu_item.get_rxmcsdr(), 'MCS-DR-TX': tu_item.get_txmcsdr(),
                                  'Power Index': tu_item.get_power_index()}
                    else:
                        record = {'Local Sector': 0, 'RSSI': -100, 'SNR': 0, 'MCS-RX': 0, 'MCS-TX': 0,
                                  'MCS-DR-RX': 0, 'MCS-DR-TX': 0, 'Power Index': 0}
                    record_series = pd.Series(record, name=time_)
                    tu_item.parameters_df = tu_item.parameters_df.append(record_series)
                    tu_counter -= 1
                if tu_counter <= 0:
                    self.next_poll = self.next_poll + self.poll_rest
            time.sleep(self.polling_inteval)
            time_ = datetime.now()
        # create the end
        test_end = datetime.now()
        self.n366.availability = self.n366.calculate_availability(self.n366.disconnection_total_time,
                                                                  self.n366.first_connection, test_end)
        self.n366.create_end(test_end)
        # we write the dataframe to excel
        # Show mesage box

        try:
            with pd.ExcelWriter(f'{self.n366.name}.xlsx', mode='w') as writer:
                self.n366.disconnections.to_excel(writer, sheet_name=f'{self.n366.name}')
                for tu_ in self.n366.tus:
                    tu__ = self.n366.tus[tu_]
                    tu__.availability = tu__.calculate_availability(tu__.disconnection_total_time, tu__.first_connection if tu__.first_connection != -1 else self.n366.first_connection, test_end)  # use start time if there is one, else use the time of the N366
                    tu__.create_end(test_end)
                    tu__.disconnections.to_excel(writer, sheet_name=f'{tu__.name}')
                    tu__.parameters_df = tu__.parameters_df.dropna(axis=0)
                    tu__.parameters_df = tu__.parameters_df.astype(int)
                    tu__.parameters_df.to_excel(writer, sheet_name=f'{tu__.name}-Parameters')
                    # We create the chart
                    worksheet = writer.sheets[f'{tu__.name}-Parameters']  # where do we want to create the chart
                    # we create the chart
                    chart = ScatterChart('smoothMarker')
                    chart.title = 'Performance metrics'
                    chart.style = 10
                    chart.x_axis.title = 'Time'
                    chart.y_axis.title = 'Metrics'
                    # we define the range of the data that will work for the X series (dates in this case)
                    # they are on the column 1 and go from row 1 to the end
                    x_values = Reference(worksheet, min_col=1, min_row=2, max_row=tu__.parameters_df.shape[0] + 1)
                    for i_ in range(2, 7):  # we walk through columns 1 to 5
                        values = Reference(worksheet, min_col=i_, min_row=1, max_row=tu__.parameters_df.shape[0] + 1)
                        series = Series(values, x_values, title_from_data=True)
                        chart.series.append(series)

                    worksheet.add_chart(chart, 'J2')
                    # end creating the chart
                    self.n366.append_end_summary(tu_, tu__.disconnections.loc['Total'])
                self.n366.disconnections_summary.to_excel(writer, sheet_name=f'Summary')
            self.running_state.emit('°D')
        except PermissionError as e:
            self.error_threads.emit('Could not write to the Excel file.')
        del (self.running_threads[self.name])

        # show message box

    def stop_thread(self):
        self.end = datetime.now()


class Tu(Qtw.QWidget):
    def __init__(self, name, parent=None):
        super(Tu, self).__init__()
        self.setParent(parent)

        # name of the widget
        self.name = name

        self.group = Qtw.QGroupBox(parent=self)

        # title of the widget name of the remote unit
        self.group.setTitle(self.name)
        # set shape, min max size
        self.group.setMinimumSize(300, 161)
        self.group.setMaximumSize(300, 161)
        # add push button that will show disconnection events
        self.btn_node = Qtw.QPushButton('Show Drop Table', parent=self.group)
        self.btn_node.setGeometry(Qtc.QRect(10, 20, 131, 23))
        # label that will whos Dic.
        self.lbl_disconnect_counter = Qtw.QLabel('Disc.', parent=self.group)
        self.lbl_disconnect_counter.setGeometry(Qtc.QRect(10, 50, 31, 16))
        # text line that will desplay the amount of disconnections
        self.txt_disconnect_counter = Qtw.QLineEdit(f'-', parent=self.group)
        self.txt_disconnect_counter.setGeometry(Qtc.QRect(40, 50, 101, 20))
        self.txt_disconnect_counter.setReadOnly(True)
        # state last disconection total time
        self.lbl_last_disc_time = Qtw.QLabel('L. drop time:', parent=self.group)
        self.lbl_last_disc_time.setGeometry(Qtc.QRect(10, 76, 72, 16))
        self.lbl_last_disc_time_value = Qtw.QLabel(f'0 s', parent=self.group)
        self.lbl_last_disc_time_value.setGeometry(Qtc.QRect(86, 76, 59, 16))
        # state the start time of last disconnection
        self.lbl_disc_time_start = Qtw.QLabel('Start disc. event:', parent=self.group)
        self.lbl_disc_time_start.setGeometry(Qtc.QRect(10, 96, 131, 16))
        self.lbl_disc_time_start_value = Qtw.QLabel('-', parent=self.group)
        self.lbl_disc_time_start_value.setGeometry(Qtc.QRect(10, 117, 131, 16))
        # state total disconection time
        self.lbl_total_disc_time = Qtw.QLabel('Tot. downtime:', parent=self.group)
        self.lbl_total_disc_time.setGeometry(Qtc.QRect(10, 135, 75, 16))
        self.lbl_total_disc_time_value = Qtw.QLabel(f'0 s', parent=self.group)
        self.lbl_total_disc_time_value.setGeometry(Qtc.QRect(91, 135, 59, 16))
        # Division
        self.line_Vertical = Qtw.QFrame(parent=self.group)
        self.line_Vertical.setGeometry(Qtc.QRect(150, 7, 2, 151))
        self.line_Vertical.setFrameShape(Qtw.QFrame.VLine)
        self.line_Vertical.setFrameShadow(Qtw.QFrame.Sunken)
        # TU parameters
        self.lbl_ls = Qtw.QLabel('L.S.:', parent=self.group)
        self.lbl_ls.setGeometry(Qtc.QRect(160, 10, 24, 16))
        self.lbl_ls_text = Qtw.QLabel('-', parent=self.group)
        self.lbl_ls_text.setGeometry(Qtc.QRect(190, 10, 10, 16))

        self.lbl_av = Qtw.QLabel('Av.:', parent=self.group)
        self.lbl_av.setGeometry(Qtc.QRect(210, 10, 24, 16))
        self.lbl_av_text = Qtw.QLabel('-', parent=self.group)
        self.lbl_av_text.setGeometry(Qtc.QRect(240, 10, 45, 16))

        self.lbl_rssi = Qtw.QLabel('RSSI:', parent=self.group)
        self.lbl_rssi.setGeometry(Qtc.QRect(160, 30, 28, 16))
        self.lbl_rssi_text = Qtw.QLabel('-128', parent=self.group)
        self.lbl_rssi_text.setGeometry(Qtc.QRect(190, 30, 25, 16))

        self.lbl_snr = Qtw.QLabel('SNR:', parent=self.group)
        self.lbl_snr.setGeometry(Qtc.QRect(230, 30, 26, 16))
        self.lbl_snr_text = Qtw.QLabel('-128', parent=self.group)
        self.lbl_snr_text.setGeometry(Qtc.QRect(260, 30, 25, 16))

        self.lbl_rx_mcs = Qtw.QLabel('RxMCS:', parent=self.group)
        self.lbl_rx_mcs.setGeometry(Qtc.QRect(160, 50, 40, 16))

        self.lbl_rx_mcs_v = Qtw.QLabel('-', parent=self.group)
        self.lbl_rx_mcs_v.setGeometry(Qtc.QRect(200, 50, 15, 16))

        self.lbl_tx_mcs = Qtw.QLabel('TxMCS:', parent=self.group)
        self.lbl_tx_mcs.setGeometry(Qtc.QRect(230, 50, 40, 16))

        self.lbl_tx_mcs_v = Qtw.QLabel('-', parent=self.group)
        self.lbl_tx_mcs_v.setGeometry(Qtc.QRect(270, 50, 15, 16))

        # self.lbl_rx_mbps = Qtw.QLabel('RxMbps:', parent=self.group)
        # self.lbl_rx_mbps.setGeometry(Qtc.QRect(160, 90, 40, 16))
        # self.lbl_rx_mbps_v = Qtw.QLabel('-', parent=self.group)
        # self.lbl_rx_mbps_v.setGeometry(Qtc.QRect(210, 90, 41, 16))

        self.lbl_tx_dr = Qtw.QLabel('Tx DR:', parent=self.group)
        self.lbl_tx_dr.setGeometry(Qtc.QRect(160, 70, 40, 16))
        self.lbl_tx_dr_v = Qtw.QLabel('-', parent=self.group)
        self.lbl_tx_dr_v.setGeometry(Qtc.QRect(210, 70, 41, 16))
        self.lbl_rx_dr = Qtw.QLabel('Rx DR:', parent=self.group)
        self.lbl_rx_dr.setGeometry(Qtc.QRect(160, 90, 40, 16))
        self.lbl_rx_dr_v = Qtw.QLabel('-', parent=self.group)
        self.lbl_rx_dr_v.setGeometry(Qtc.QRect(210, 90, 41, 16))

        self.lbl_tx_index = Qtw.QLabel('Tx Index:', parent=self.group)
        self.lbl_tx_index.setGeometry(Qtc.QRect(160, 110, 50, 16))
        self.lbl_tx_index_v = Qtw.QLabel('-', parent=self.group)
        self.lbl_tx_index_v.setGeometry(Qtc.QRect(210, 110, 41, 16))

        # create the layout
        widget_layout = Qtw.QGridLayout()
        widget_layout.addWidget(self.group, 0, 0, 1, 1)

        self.setLayout(widget_layout)

    @Qtc.pyqtSlot(int)
    def update_ls(self, ls):
        self.lbl_ls_text.setText(f'{ls}')

    @Qtc.pyqtSlot(int)
    def update_rssi(self, rssi):
        self.lbl_rssi_text.setText(f'{rssi}')

    @Qtc.pyqtSlot(int)
    def update_snr(self, snr):
        self.lbl_snr_text.setText(f'{snr}')

    @Qtc.pyqtSlot(int)
    def update_rxmcs(self, rxmcs):
        self.lbl_rx_mcs_v.setText(f'{rxmcs}')

    @Qtc.pyqtSlot(int)
    def update_txmcs(self, txmcs):
        self.lbl_tx_mcs_v.setText(f'{txmcs}')

    @Qtc.pyqtSlot(int)
    def update_tx_power_index(self, txpower):
        self.lbl_tx_index_v.setText(f'{txpower}')

    # @Qtc.pyqtSlot(float)
    # def update_rxmcs_v(self, rxsp):
    #     self.lbl_rx_mbps_v.setText(f'{rxsp}')
    #
    # @Qtc.pyqtSlot(float)
    # def update_txmcs_v(self, txsp):
    #     self.lbl_tx_mbps_v.setText(f'{txsp}')

    @Qtc.pyqtSlot(int)
    def update_rx_dr(self, dr):
        self.lbl_rx_dr_v.setText(f'{dr}')

    @Qtc.pyqtSlot(int)
    def update_tx_dr(self, dr):
        self.lbl_tx_dr_v.setText(f'{dr}')

    @Qtc.pyqtSlot(float)
    def update_av(self, av):
        self.lbl_av_text.setText(f'{av:.2f}%')

    @Qtc.pyqtSlot(int)
    def update_d_counter(self, counter_):
        self.txt_disconnect_counter.setText(f'{counter_}')

    @Qtc.pyqtSlot(timedelta)
    def update_d_ldt(self, time_):
        self.lbl_last_disc_time_value.setText(f'{time_}')

    @Qtc.pyqtSlot(datetime)
    def update_d_lds(self, time_):
        self.lbl_disc_time_start_value.setText(f'{time_}')

    @Qtc.pyqtSlot(timedelta)
    def update_d_tdt(self, time_):
        self.lbl_total_disc_time_value.setText(f'{time_}')

    @Qtc.pyqtSlot(bool)
    def update_connection_status(self, status):
        if status:
            self.setStyleSheet('background-color: rgb(85, 170, 0);')
        else:
            self.setStyleSheet('background-color: rgb(255, 41, 41);')


class N366Widget(Qtw.QWidget):

    def __init__(self, n366_node, run_time, poll_time, poll_rest, parent=None):
        super(N366Widget, self).__init__(parent)
        self.n366 = n366_node  # N366 BU datanode
        self.tu_items = {}  # TU widget dictionary

        # Variables to fit the nodes inside the widget to add 60
        self.columns = 5
        self.rows = 60 / self.columns
        # The x,y coordinates to add new nodes
        self.current_row = 1
        self.current_column = 0
        # Label remaining test time
        lbl_time_remaining_label = Qtw.QLabel('Remaining test time: ')
        self.lbl_time_remaining = Qtw.QLabel('-')

        # layout on the widget
        self.layout_design = Qtw.QGridLayout()
        self.layout_design.addWidget(lbl_time_remaining_label, 0, 0, 1, 1)
        self.layout_design.addWidget(self.lbl_time_remaining, 0, 1, 1, 1)
        tu_nodes = self.n366.tus

        for tu_ in tu_nodes:  # create the node widgets
            if tu_ not in self.tu_items:
                self.tu_items[tu_] = Tu(tu_, parent=self)
            self.add_widget(self.tu_items[tu_])

        thread = CheckingThread(self.n366.name, self.n366, run_time, poll_time, poll_rest)
        # ----------------------- MUY IMPORTANTE PARA QUE NO SE ROMPA EN WINDOWS
        # tenemos que ponerle un padre al hilo para que no lo destruya windows
        thread.setParent(self)
        # ----------------------- MUY IMPORTANTE PARA QUE NO SE ROMPA EN WINDOWS
        thread.start()

        thread.answer_thread.connect(self.update_values)
        thread.running_state.connect(self.update_tab_info)
        thread.remaining_time.connect(self.update_remaining_time)

        self.setLayout(self.layout_design)

    @Qtc.pyqtSlot(str, list)
    def update_values(self, name_, values_):
        if name_ not in self.tu_items:
            self.tu_items[name_] = Tu(name_, parent=self)
            self.add_widget(self.tu_items[name_])
        self.tu_items[name_].update_ls(values_[0])  # Local Sector
        self.tu_items[name_].update_rssi(values_[1])  # RSSI
        self.tu_items[name_].update_snr(values_[2])  # SNR
        self.tu_items[name_].update_rxmcs(values_[3])  # RX MCS
        self.tu_items[name_].update_txmcs(values_[4])  # TX MCS
        # self.tu_items[name_].update_rxmcs_v(values_[5])  # RX MCS Speed MBPS
        # self.tu_items[name_].update_txmcs_v(values_[6])  # TX MCS Speed MBPS
        self.tu_items[name_].update_rx_dr(values_[7])  # RX MCS DR
        self.tu_items[name_].update_tx_dr(values_[8])  # TX MCS DR
        self.tu_items[name_].update_av(values_[9])  # TU Availability
        self.tu_items[name_].update_d_counter(values_[10])  # Disconnection Counter
        self.tu_items[name_].update_d_ldt(values_[11])  # Drop time of last event
        self.tu_items[name_].update_d_lds(values_[12])  # Drop time start of event
        self.tu_items[name_].update_d_tdt(values_[13])  # Total disconnection time
        self.tu_items[name_].update_connection_status(values_[14])  # Update connection status (colors)
        self.tu_items[name_].update_tx_power_index(values_[15])  # Update Tx Power index

    def add_widget(self, widget):
        """
        Function that will add a widget to the N366 layout in a grid x, y
        :param widget: widget to be added into the N366 widget
        :return:
        """
        # set the new widget in a manner x, y
        self.layout_design.addWidget(widget, self.current_row, self.current_column, 1, 1)
        # update the column to move to the new place
        self.current_column += 1
        # if we reach the max number of columns we reset the column and add a row
        if self.current_column == self.columns:
            self.current_column = 0
            self.current_row += 1

    @Qtc.pyqtSlot(str)
    def update_tab_info(self, status):
        tab_parent = self.parent().parent()
        tabs = [tab_parent.tabText(i) for i in range(len(tab_parent))]
        if status == '°D':
            self.lbl_time_remaining.setText('0:00:00')
        for index, name_ in enumerate(tabs):
            if self.n366.name == name_:  # process just started updating it to -R
                tab_parent.setTabText(index, f'{self.n366.name}-{status}')
            elif f'{self.n366.name}-°R' == name_:
                tab_parent.setTabText(index, f'{self.n366.name}-{status}')
            elif f'{self.n366.name}-°D' == name_:
                tab_parent.setTabText(index, f'{self.n366.name}-{status}')
            elif f'{self.n366.name}-°RC' == name_:
                tab_parent.setTabText(index, f'{self.n366.name}-{status}')

    @Qtc.pyqtSlot(str)
    def update_remaining_time(self, remining_time_):
        time = remining_time_[:remining_time_.rfind('.')]
        self.lbl_time_remaining.setText(time)


class NetconfMonitorWidget(Qtw.QWidget):

    status_message = Qtc.pyqtSignal(str)

    def __init__(self, parent):
        super(NetconfMonitorWidget, self).__init__()

        # Create the tabs widget
        self.tabs = Qtw.QTabWidget()
        self.tabs.setObjectName('TabsRoot')
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(True)
        # create an empty widget that will be displayed on the tab
        self.tab_root = Qtw.QWidget()
        self.tab_root.setObjectName('WidgetRoot')
        # Set size of the widget
        self.tabs.resize(600, 800)

        # Add new tab with name N366
        self.tabs.addTab(self.tab_root, "Add N366")
        # name holder
        self.lbl_name = Qtw.QLabel('Name:')

        self.txt_name = Qtw.QLineEdit('')
        self.txt_name.setPlaceholderText('Name for the new Tab')

        self.txt_user = Qtw.QLineEdit('')
        self.txt_user.setPlaceholderText('username')

        self.txt_pass = Qtw.QLineEdit('')
        self.txt_pass.setPlaceholderText('password')
        self.txt_pass.setEchoMode(Qtw.QLineEdit.Password)

        # Label
        self.lbl_ip = Qtw.QLabel('IP:')
        # holder for IP
        self.txt_ip = Qtw.QLineEdit('')

        self.lbl_poll_interval = Qtw.QLabel('Poll interval (seconds):')
        # Holder for seconds, every X seconds go fetch info
        self.spn_poll_interval = Qtw.QSpinBox()
        self.spn_poll_interval.setValue(1)

        self.lbl_time_to_run = Qtw.QLabel('Duration (minutes):')
        # Holder for minutes, how many minutes the poll will last
        self.spn_time_to_run = Qtw.QSpinBox()
        self.spn_time_to_run.setMaximum(43200)
        self.spn_time_to_run.setValue(5)

        self.txt_ip.setPlaceholderText('Enter ip of N366')

        # Add a label and a spinner to save the other parameters of the radio
        self.lbl_poll_interval_rest = Qtw.QLabel('Poll RF params. (seconds):')
        self.spn_poll_interval_rest = Qtw.QSpinBox()
        self.spn_poll_interval_rest.setMaximum(86400)
        self.spn_poll_interval_rest.setMinimum(0)
        self.spn_poll_interval_rest.setValue(5)

        self.btn_addn366 = Qtw.QPushButton('Add N366')

        # clicks and connection handling
        self.btn_addn366.clicked.connect(self.addtab)  # add new tab with desired info
        self.tabs.tabCloseRequested.connect(self.closetab)  # close tab that is not main

        # shortcuts
        # Change fotn size grow
        shortcut_size_grow = Qtw.QShortcut(Qtg.QKeySequence('Ctrl++'), self)
        shortcut_size_grow.setObjectName('shortcut_size_grow')
        shortcut_size_grow.activated.connect(self.change_font_size_grow)

        # Change fotn size small
        shortcut_size_shrink = Qtw.QShortcut(Qtg.QKeySequence('Ctrl+-'), self)
        shortcut_size_shrink.setObjectName('shortcut_size_shrink')
        shortcut_size_shrink.activated.connect(self.change_font_size_shrink)

        # add the layout of the empty widget
        self.tab_root.layout = Qtw.QGridLayout()
        self.tab_root.layout.addWidget(self.lbl_name, 0, 0, 1, 1)
        self.tab_root.layout.addWidget(self.txt_name, 0, 1, 1, 1)
        self.tab_root.layout.addWidget(self.lbl_ip, 1, 0, 1, 1)
        self.tab_root.layout.addWidget(self.txt_ip, 1, 1, 1, 1)
        self.tab_root.layout.addWidget(self.txt_user, 2, 0, 1, 1)
        self.tab_root.layout.addWidget(self.txt_pass, 2, 1, 1, 1)
        self.tab_root.layout.addWidget(self.lbl_poll_interval, 3, 0, 1, 1)
        self.tab_root.layout.addWidget(self.spn_poll_interval, 3, 1, 1, 1)
        self.tab_root.layout.addWidget(self.lbl_time_to_run, 4, 0, 1, 1)
        self.tab_root.layout.addWidget(self.spn_time_to_run, 4, 1, 1, 1)
        self.tab_root.layout.addWidget(self.lbl_poll_interval_rest, 5, 0, 1, 1)
        self.tab_root.layout.addWidget(self.spn_poll_interval_rest, 5, 1, 1, 1)
        self.tab_root.layout.addWidget(self.btn_addn366, 6, 0, 1, 2)
        self.tab_root.setLayout(self.tab_root.layout)
        # add the layout of the tabs to the widget that will be shown
        layout = Qtw.QGridLayout()
        layout.addWidget(self.tabs)

        self.setLayout(layout)

    def change_font_size_grow(self):
        font = self.font()
        font.setPointSize(font.pointSize() + 1)
        self.setFont(font)

    def change_font_size_shrink(self):
        font = self.font()
        font.setPointSize(font.pointSize() - 1)
        self.setFont(font)

    @Qtc.pyqtSlot(str)
    def send_answer(self, message):
        self.status_message.emit(message)

    def addtab(self):  # agrega un tab
        """
        Adds new tab only if the name doesn't exists in the tabs
        :return: None
        """
        # add a new tab with the widget
        tabs = [self.tabs.tabText(i) if '-°' not in self.tabs.tabText(i) else
                self.tabs.tabText(i)[:self.tabs.tabText(i).find('-°')]
                for i in range(len(self.tabs))]  # get all tab names and remove status marker °R or °D
        if self.txt_name.text() not in tabs and self.txt_name.text() != '':  # if name is new and not empty

            # creating the object to pass to the widget
            node_366 = BU366(self.txt_name.text(), self.txt_ip.text())
            # establishing the connection
            try:
                node_366.first_contact(self.txt_user.text(), self.txt_pass.text(), 22, 5)
                # creating the widget
                widget_n366 = N366Widget(node_366, self.spn_time_to_run.value(), self.spn_poll_interval.value(),
                                         self.spn_poll_interval_rest.value(), parent=self)
                # adding the widget to the tab
                self.tabs.addTab(widget_n366, f'{self.txt_name.text()}')
                self.status_message.emit(f'{self.txt_name.text()} tab correctly added')  # send message to status bar
            except socket.gaierror as e:
                self.status_message.emit('The IP is not valid. Please set a valid IP')
            except ValueError as e:
                self.status_message.emit('The username or password is wrong please try again')
            except AttributeError as e:
                self.status_message.emit('The unit is not able to respond. Check there is a link to it')
            except:
                self.status_message.emit(f'Something really really bad happened error')
        else:
            self.status_message.emit('The name already exists, please select another one')

    # close tab get's a signal as an input
    @Qtc.pyqtSlot(int)
    def closetab(self, index):
        if self.tabs.tabText(index) != 'Add N366':  # check that it is not the main tab
            self.status_message.emit(f'{self.tabs.tabText(index)} - removed')
            # we get the nodes to check the thread we want to stop
            nodes = self.tabs.children()[0].children()  # this gets the N366 nodes
            for node in nodes:  # we iterate over all the nodes
                if isinstance(node, N366Widget):  # if the node is N366widget
                    tab_text = self.tabs.tabText(index)
                    # if the name of the N366widget = the name we want to close
                    if node.n366.name == tab_text[:tab_text.rfind('-°')]:
                        if node.n366.name in CheckingThread.running_threads:
                            CheckingThread.running_threads[node.n366.name].stop_thread()

            # Finishing closing the thread
            self.tabs.removeTab(index)


class MainWindow(Qtw.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        # -------------------- widget creation
        self.setWindowTitle('TG-Monitor V1.0')
        self.monitor = NetconfMonitorWidget(self)
        # -------------------- widget layout
        self.setCentralWidget(self.monitor)
        self.statusBar().setVisible(True)
        # -------------------- widget connections and actions
        self.monitor.status_message.connect(self.status_display)

        # -------------------- Window Icon
        windows_icon = Qtg.QIcon('Logo-Icon.png')
        self.setWindowIcon(windows_icon)

        self.show()

    @Qtc.pyqtSlot(str)
    def status_display(self, message_):
        self.statusBar().showMessage(f'{message_}', 2000)

    def closeEvent(self, event):
        msg_box_answer = Qtw.QMessageBox(
            Qtw.QMessageBox.Critical,
            'Finishing process',
            '1. The Monitor is aboout to close.\n'
            '2. It will start generating the reports.\n'
            '3. Depending on the time it was running it might take a few minutes to generate the files.\n'
            '4. Consider each TU might generate up to 240MB per 24 hours of test. (that is a big file)\n'
            '5. Be patient while we run the process, after it the app will close.\n\n'
            '6. The process will start after closing this message', Qtw.QMessageBox.Ok)
        a = msg_box_answer.exec_()
        tabs = [self.monitor.tabs.tabText(index_) for index_ in range(len(self.monitor.tabs))]  # get the tabs
        tabs = [tab_name[:tab_name.rfind('-°')] for tab_name in tabs if tab_name != 'Add N366']  # process the tabs to remove status messages
        nodes = self.monitor.tabs.children()[0].children()  # gets the N366 items
        for node in nodes:
            if isinstance(node, N366Widget):  # if the node is an N366Widget
                if node.n366.name in CheckingThread.running_threads:  # if the thread is still running
                    CheckingThread.running_threads[node.n366.name].stop_thread()
        while len(CheckingThread.running_threads):
            self.status_display('Waiting on Threads to finish')
        self.status_display('Closing app')


def main():
    app = Qtw.QApplication(sys.argv)
    app.setOrganizationName('Javopan Awesome Systems')
    app.setOrganizationDomain('javoisawesome.com')
    app.setApplicationName('TG-Mon')
    # app.setStyleSheet(open('Styles.css', 'r', encoding='utf-8').read())
    mw = MainWindow()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
