from ncclient import manager, transport


class SikluNetconf:
    def __init__(self, ip, user='admin', password='admin', port=22, timeout=5, device_params={'name': 'nexus'},
                 hostkey_verify=False):
        self.ip = ip
        self.username = user
        self.password = password
        self.port = port
        self.timeout = timeout
        self.device_params = device_params
        self.host_key = hostkey_verify
        self.channel = None

    def get_command(self, command_):
        """
                This fuction will send the commands to the radio via NetCONF.
                :param command_:
                Command will be the command to check, working on execution
                :return:
                tree output
                """
        return self.channel.get(command_)

    def connect(self):
        """
        Creates a connection with the given parameters via a Netconf Shell.
        By default it will auto add keys
        :return: True if connection successfully connected, False if not
        """
        try:
            self.channel = manager.connect(host=self.ip, port=self.port, username=self.username, password=self.password,
                                           device_params=self.device_params, hostkey_verify=self.host_key)
            return True
        except transport.SSHError as e:
            print(f'Could not connect. Please check the device is enabled.\nActual python error: {e}')
            return False
        except transport.AuthenticationError as e:
            print(f'Could not connect. Bad user/pass combination. Please review.\nActual python error: {e}')
            raise ValueError('Bad Username or Password')
        except transport.TransportError as e:
            print(f'Connection suddenly broke\nActual python error: {e}')
            raise ValueError('Sudden disconnection')

    def close(self):
        self.channel.close_session()


if __name__ == '__main__':
    ip = '31.168.34.110'
    command = ''

    n366 = SikluNetconf(ip, 'admin', 'TGadmin1')
    n366.connect()
    n366_active = n366.get_command('<filter xmlns:n366="http://siklu.com/yang/tg/radio" select="/n366:radio-common/n366:links/n366:active/n366:remote-assigned-name" type="xpath"/>')
    print(n366_active)
    n366_conf = n366.get_command('<filter xmlns:n366="http://siklu.com/yang/tg/radio/dn" select="/n366:radio-dn/n366:links" type="xpath"/>')
    print(n366_conf)

    print('The_end')
