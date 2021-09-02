from datetime import datetime, timedelta
from collections import deque, OrderedDict
from Netconf_Driver import SikluNetconf
from tu_data_model import TuDataModel
from itertools import zip_longest
from ncclient import transport
import pandas as pd


class BU366:
    """
    A class that will hold TU's for N366 and ip and name and connection information for each N366. The N366 will give
    us all the info on the TU. The TU are only placeholders on the information

    No private variables should be used directly. All should be managed via setters and getters
    """

    def __init__(self, name_, ip_):

        # name of the N366 BU it needs to be unique
        self.name = name_
        # IP address for the unit
        self.ip = ip_
        # Password
        self.password = None
        # username
        self.username = None
        # dictionary of TU's
        self.tus = {}
        # connection
        self.connection = None
        # number of registered devices
        self.registered_devices = 0
        # number of connected
        self.connected_devices = 0

        # beginning of time from 1st connection
        self.first_connection = -1
        # self disconnection counter
        self.disconnetions_counter = 0
        # management of disconnections event
        self.disconnection_start = None  # start of event
        self.disconnection_end = None  # end of event
        self.connection_state = False  # state of the connection
        self.disconnection_last_event_time = timedelta(seconds=0)  # the total time of last disconnection
        # total disconnection time
        self.disconnection_total_time = timedelta(seconds=0)
        # total actual availability
        self.availability = 100.0
        # disconnections dataframe to have the list
        # we need to append with a pd.Series(data_in_a_dict, name=datetime.now()/or time)
        self.disconnections = pd.DataFrame(columns=['Time End', 'Disconnection #', 'Downtime', 'Availability'])
        # We create a summary dataframe to print at the end where all the info is
        self.disconnections_summary = pd.DataFrame(columns=['Time End', 'Disconnection #', 'Downtime',
                                                            'Availability'])

    def connect(self, user, password,  port, timeout=5):
        """
        this will stablish the connection to the DN via NETCONF
        :param user: str, username
        :param password: str, password
        :param port: int, port to connect
        :param timeout: int, timeout for the connection
        :return: boo, if the connection was successful
        """
        self.connection = SikluNetconf(self.ip, user, password, port, timeout)  # we try to connect to the N366
        if self.connection.connect():  # if connection is successful
            self.username = user  # we store username
            self.password = password  # we store password
            if self.first_connection == -1:  # if the connection is the first connection
                self.first_connection = datetime.now()  # store first contact to calculate availability
            else:  # we are reconnecting
                self.disconnection_end = datetime.now()  # store the end of the drop
                # record the total time of the last event
                self.disconnection_last_event_time = self.disconnection_end - self.disconnection_start
                # add the disconnection time to the total drop time of all events
                self.disconnection_total_time += self.disconnection_end - self.disconnection_start  # add to the total
                # drop time of the N366

                # calculate availability
                availability = self.calculate_availability(self.disconnection_total_time, self.first_connection,
                                                           self.disconnection_end)
                self.availability = availability
                # update 1 : update time end
                self.disconnections = self.update_record(self.disconnections, self.disconnection_start, 'Time End',
                                                         self.disconnection_end)
                # update 2: update duration of the desconnection
                self.disconnections = self.update_record(self.disconnections, self.disconnection_start, 'Downtime',
                                                         f'{self.disconnection_last_event_time}')
                # update 3: update of the availability
                self.disconnections = self.update_record(self.disconnections, self.disconnection_start, 'Availability',
                                                         availability)
                # update 4: update of disconnection#
                self.disconnections = self.update_record(self.disconnections, self.disconnection_start,'Disconnection #',
                                                         self.disconnetions_counter)

            self.connection_state = True  # change state to up.
            return True
        return False

    def send_message(self, message):
        """
        sends a message via NETCONF and returns it
        :param message: str, message to send
        :return: xlmx, element
        """
        try:
            answer = self.connection.get_command(message)
            return answer
        except AttributeError as e:
            print(f'No connection exists. Please connect to the unit before sending a command.\nOriginal error: {e}')
            return None
        except transport.errors.SessionCloseError as e:  # the connection broke we need to start logging it
            break_time = datetime.now()
            self.disconnection_start = break_time  # We set the disconnection time
            self.connection_state = False  # we set the connection indicator to false
            self.disconnetions_counter += 1
            for tus_ in self.tus:
                self.tus[tus_].disconnected(break_time)
            return None

    def get_active_links(self):
        """
        sends message to get active links + info on all relevant information
        :return: dict, active links and information relevant to the link
        """
        # Message to send via netconf
        message_act_links = '<filter xmlns:n366="http://siklu.com/yang/tg/radio" select="/n366:radio-common/' \
                            'n366:links/n366:active" type="xpath"/>'
        act_links_ans = self.send_message(message_act_links)

        # Dictionary that will hold the answer of each link
        act_links_answer = OrderedDict()

        # NAMESPACE TO GET THE INFO FROM THE RADIO SECTION
        namespace = {'n366': 'http://siklu.com/yang/tg/radio'}

        # get the link names
        ln_xpath = 'n366:links/n366:active/n366:remote-assigned-name/text()'
        act_links_names = self.process_netconf_answer(act_links_ans, ln_xpath, namespace)
        if act_links_names == -1:  # there were no connections established
            act_links_names = []

        # get local sector, The NAMESPACE STAYS THE SAME
        ls_xpath = 'n366:links/n366:active/n366:actual-local-sector-index/text()'
        ls_ans = self.process_netconf_answer(act_links_ans, ls_xpath, namespace)
        if ls_ans == -1:  # there were no connections established
            ls_ans = []

        # get rssi, The NAMESPACE STAYS THE SAME
        rssi_xpath = 'n366:links/n366:active/n366:rssi/text()'
        rssi_ans = self.process_netconf_answer(act_links_ans, rssi_xpath, namespace)
        if rssi_ans == -1:  # there were no connections established
            rssi_ans = []

        # get snr, The NAMESPACE STAYS THE SAME
        snr_xpath = 'n366:links/n366:active/n366:snr/text()'
        snr_ans = self.process_netconf_answer(act_links_ans, snr_xpath, namespace)
        if snr_ans == -1:  # there were no connections established
            snr_ans = []

        # get mcs-rx, The NAMESPACE STAYS THE SAME
        mcsrx_xpath = 'n366:links/n366:active/n366:mcs-rx/text()'
        mcsrx_ans = self.process_netconf_answer(act_links_ans, mcsrx_xpath, namespace)
        if mcsrx_ans == -1:  # there were no connections established
            mcsrx_ans = []


        # get mcs-tx, The NAMESPACE STAYS THE SAME
        mcstx_xpath = 'n366:links/n366:active/n366:mcs-tx/text()'
        mcstx_ans = self.process_netconf_answer(act_links_ans, mcstx_xpath, namespace)
        if mcstx_ans == -1:  # there were no connections established
            mcstx_ans = []

        # get per-rx, The NAMESPACE STAYS THE SAME
        rxper_xpath = 'n366:links/n366:active/n366:rx-per/text()'
        rxper_ans = self.process_netconf_answer(act_links_ans, rxper_xpath, namespace)
        if rxper_ans == -1:  # there were no connections established
            rxper_ans = []

        # get per-tx, The NAMESPACE STAYS THE SAME
        txper_xpath = 'n366:links/n366:active/n366:tx-per/text()'
        txper_ans = self.process_netconf_answer(act_links_ans, txper_xpath, namespace)
        if txper_ans == -1:  # there were no connections established
            txper_ans = []

        # get speed_dr, The NAMESPACE STAYS THE SAME
        speedrx_xpath = 'n366:links/n366:active/n366:speed-rx/text()'
        speedrx_ans = self.process_netconf_answer(act_links_ans, speedrx_xpath, namespace)
        if speedrx_ans == -1:  # there were no connections established
            speedrx_ans = []

        # get speed_dr, The NAMESPACE STAYS THE SAME
        speedtx_xpath = 'n366:links/n366:active/n366:speed-tx/text()'
        speedtx_ans = self.process_netconf_answer(act_links_ans, speedtx_xpath, namespace)
        if speedtx_ans == -1:  # there were no connections established
            speedtx_ans = []

        # get Tx-power-index, The NAMSPACE STAYS THE SAME
        tx_power_xpath ='n366:links/n366:active/n366:tx-power-index/text()'
        tx_power_ans = self.process_netconf_answer(act_links_ans, tx_power_xpath, namespace)
        if tx_power_ans == -1:  # There is no connections established
            tx_power_ans = []

        answers_zip = zip_longest(act_links_names, ls_ans, rssi_ans, snr_ans, mcsrx_ans, mcstx_ans, rxper_ans,
                                  txper_ans, speedrx_ans, speedtx_ans, tx_power_ans)
        # 0 Link names
        # 1 local sector
        # 2 rssi
        # 3 snr
        # 4 mcs_rx
        # 5 mcs_tx
        # 6 rx-per
        # 7 tx-per
        # 8 speed-rx
        # 9 speed-tx

        # to do after i got all the answers for a single loop in a zip
        # add the local sector to the dictionary to complement the answer
        for link in answers_zip:
            if link[0] not in act_links_answer:  # new link we need to add it to the dictionary:
                act_links_answer[link[0]] = {}
            # The link is already in the dictionary so we just add the elements
            act_links_answer[link[0]]['Local Sector'] = link[1]
            act_links_answer[link[0]]['RSSI'] = link[2]
            act_links_answer[link[0]]['SNR'] = link[3]
            act_links_answer[link[0]]['mcs-rx'] = link[4]
            act_links_answer[link[0]]['mcs-tx'] = link[5]
            act_links_answer[link[0]]['rx-per'] = link[6]
            act_links_answer[link[0]]['tx-per'] = link[7]
            act_links_answer[link[0]]['speed-rx'] = link[8]
            act_links_answer[link[0]]['speed-tx'] = link[9]
            act_links_answer[link[0]]['tx-power'] = link[10]

        return act_links_answer

    def get_registered_links(self):
        """
        sends message to get registered links
        :return: list, registered links
        """
        message_reg_links = '<filter xmlns:n366="http://siklu.com/yang/tg/radio/dn" select="/n366:radio-dn/' \
                            'n366:links" type="xpath"/>'
        reg_links_ans = self.send_message(message_reg_links)
        xpath = 'n366:links/n366:configured/n366:remote-assigned-name/text()'
        namespace = {'n366': 'http://siklu.com/yang/tg/radio/dn'}
        reg_links = self.process_netconf_answer(reg_links_ans, xpath, namespace)
        return reg_links

    def process_netconf_answer(self, netconf_msg, xpath, namespace):
        """
        Processes a netconf message to return the text
        :param netconf_msg: ncclient answer
        :param xpath: str, xpath address in a tree to get the answe
        :param namespace: dict, dictionary with the xlmns
        :return: list, with answer
        """
        processed_msg = -1
        if len(netconf_msg.data) > 0:
            processed_msg = netconf_msg.data[0].xpath(xpath, namespaces=namespace)
        return processed_msg

    def add_tu(self, name_):
        """
        Adds a TU to the disctionary of TU's
        :param name_: str, name of the tu to add
        :return: bool, if the tu was correctly added to the self.tus dictionary
        """
        if name_ not in self.tus.keys():
            try:
                self.tus[name_] = TuDataModel(name_)
                return True
            # catches all the expetions, this is a wide range but many things could happen
            except Exception as e:
                print(f'We had an error adding a TU to the tus dictionary.\nPython original message: {e}')
                return False
        else:
            print(f'We already have an object with that name in the dictionary.')
            return False

    def first_contact(self, username, password, port, timeout):
        """
        This will do the process to connect to a N366 and get the registered units, create the TU's in the dictionary
        :param username: str, username to connect
        :param password: str, password to connect
        :param port: int, connection port
        :param timeout: int, time of connection timeout
        :return: bool, True if all the process was done correctly, false other wise
        """
        # establish a connection
        self.connect(username, password, port, timeout)
        # get the registered links
        reg_links = self.get_registered_links()
        # process the list to add the TU's
        for reg in reg_links:
            try:
                self.add_tu(reg)
            except Exception as e:
                print(f'Error while trying to add a new TU to the dictionary.\nOriginal python error{e}')
        self.registered_devices = len(reg)

    def check_active(self):
        """
        will check and update the links, active and registered. It will also connect and disconnect them based on the
        answer from the get_active_links and get_registered_links(). It will also add new links. But won't remove
        deleted links for control
        :return:
        """
        a_links = self.get_active_links()  # get active links
        r_links = self.get_registered_links()  # get registered links
        self.connected_devices = len(a_links)
        for link in a_links:  # we check if the active links are in the tus dict
            if link in self.tus:
                self.tus[link].connected(datetime.now())  # if they are we connect them
            else:  # is active but not previously registered!! We need to add it to the tu's dict
                self.add_tu(link)
                self.tus[link].connected(datetime.now())
            self.tus[link].set_local_sector(a_links[link]['Local Sector'])
            self.tus[link].set_rssi(a_links[link]['RSSI'])
            self.tus[link].set_snr(a_links[link]['SNR'])
            self.tus[link].set_rxmcs(a_links[link]['mcs-rx'])
            self.tus[link].set_txmcs(a_links[link]['mcs-tx'])
            self.tus[link].set_rxspeednum(a_links[link]['rx-per'])
            self.tus[link].set_txspeednum(a_links[link]['tx-per'])
            self.tus[link].set_rxmcsdr()
            self.tus[link].set_txmcsdr()
            self.tus[link].set_power_index(a_links[link]['tx-power'])
        # check what links are registered but not active. we need to disconnect them
        self.registered_devices = len(r_links)
        for r_link in r_links:
            if r_link not in a_links:  # registered but not active
                if r_link not in self.tus:  # new registered link
                    self.add_tu(r_link)  # add to the dictionary
                self.tus[r_link].disconnected(datetime.now())
            else:
                if r_link not in self.tus:  # new registered link
                    self.add_tu(r_link)
                    self.tus[r_link].connected(datetime.now())

    @staticmethod
    def calculate_availability(time_span, start_t, time_t):
        """
        Calculate availability of time_span from start to time
        :param time_span: datetime, time where we can to calculate availability
        :param start_t: datetime, start time to calculate availability
        :param time_t: datetime, time to calculate availability
        :return:  float, availability
        """
        if start_t == -1:  # the unit was never connected
            return 0
        return (1 - (time_span / (time_t - start_t))) * 100

    @staticmethod
    def update_record(df, find_variable, field, update_data):
        df.loc[find_variable, field] = update_data
        return df

    def create_end(self, time_end):
        end_ = pd.Series(
            {'Time End': time_end, 'Disconnection #': self.disconnetions_counter,
             'Downtime': f'{self.disconnection_total_time}',
             'Availability': self.availability if self.first_connection != -1 else 0}, name='Total')
        self.disconnections = self.disconnections.append(end_)
        # Change type of columns to print in excel to proper value
        self.disconnections['Disconnection #'] = self.disconnections['Disconnection #'].astype(int)
        self.disconnections['Availability'] = self.disconnections['Availability'].astype(float)
        end_summary_ = pd.Series(
            {'Time End': time_end, 'Disconnection #': self.disconnetions_counter,
             'Downtime': f'{self.disconnection_total_time}',
             'Availability': self.availability if self.first_connection != -1 else 0}, name=self.name)
        # Change the column type to print in excel
        self.disconnections_summary = self.disconnections_summary.append(end_summary_)
        self.disconnections_summary['Disconnection #'] = self.disconnections_summary['Disconnection #'].astype(int)
        self.disconnections_summary['Availability'] = self.disconnections_summary['Availability'].astype(float)

    def append_end_summary(self, name_, record):
        record_dic = record.to_dict()
        self.disconnections_summary = self.disconnections_summary.append(pd.Series(record_dic, name=name_))


if __name__ == '__main__':
    # Test 1 item per item
    # n366 = BU366('Prueba', '31.168.34.110')
    # n366.connect('admin', 'TGadmin1', 22, 5)
    # print(n366.send_message('<filter xmlns:n366="http://siklu.com/yang/tg/radio" select="/n366:radio-common/n366:links/'
    #                         'n366:active/n366:remote-assigned-name" type="xpath"/>'))
    # print(n366.get_registered_links())
    # print(n366.get_active_links())
    # Test 2 automated
    name = 'Prueba'
    ip = '31.168.34.110'
    n366 = BU366(name, ip)
    user_n = 'admin'
    pass_w = 'TGadmin1'
    n366.first_contact(user_n, pass_w, 22, 5)
    # prints the tus
    print(n366.tus)
    # check if the tu's ar active
    p = 0
    while p < 100:
        start = datetime.now()
        n366.check_active()
        print(datetime.now() - start)
        p += 1
