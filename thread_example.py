import threading
import bu_data_model
import datetime
import time
import random


class myThread(threading.Thread):
    def __init__(self, threadid_, n366, total_time, polling_interval):
        threading.Thread.__init__(self)
        self.threadid = threadid_
        self.name = n366.name
        self.n366 = n366
        self.total_time = total_time
        self.polling_inteval = polling_interval
        self.end = datetime.datetime.now() + datetime.timedelta(minutes=total_time)

    def run(self):
        print(f'starting Thread: {self.name} - {datetime.datetime.now()}')
        print(f'Checking time: {self.total_time}')
        print(f'Polling interval: {self.polling_inteval}')
        while datetime.datetime.now() < self.end:
            self.n366.check_active()
            time.sleep(self.polling_inteval)
        for tu in self.n366.tus:
            self.n366.tus[tu].print()
        print(f'Exiting Thread: {self.name} - {datetime.datetime.now()}')


name = 'Prueba_1'
ip = '31.168.34.110'
user_n = 'admin'
pass_w = 'TGadmin1'
n366_1 = bu_data_model.BU366(name, ip)
n366_1.first_contact(user_n, pass_w, 22, 5)
n366_2 = bu_data_model.BU366('Prueba_2', ip)
n366_2.first_contact(user_n, pass_w, 22, 5)

end = datetime.datetime.now() + datetime.timedelta(minutes=5)
i = 0
while True and bu_data_model.BU366.n366_queue:
    element = bu_data_model.BU366.n366_queue.popleft()
    thread = myThread(i + 1, element, random.randint(1, 3), random.randint(1, 10))
    thread.start()
    if i == 0:
        n366_1 = bu_data_model.BU366(f'Prueba_3', ip)
        n366_1.first_contact(user_n, pass_w, 22, 5)
    i += 1
print('\ndone')
