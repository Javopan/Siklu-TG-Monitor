# Siklu-TG-Monitor
A tool to monitor Siklu's DN nodes and have a visual guide on connected TU's + graph it in excel

The idea of the tool is to have a big loop that will contact the DN at a given time and then smaller loops that will pool the RF parameters when needed.
The tool uses PyQT5 for the GUI so that the script can be run platform independent (Windows,Linux, Mac).

required packages to be able to run the script:

* PyQT5 - GUI & slot and signals framework  
* lxml - parsing the answers of the TG device  
* ncclient - building and sending the xml messages to the unit  
* pandas - dataframe framework to manage the information retrived and to write it to excel  
* openpyxl - excel writter  

Many thanks and credit to the teams behind this python modules (Women and Men)

# Usage

run the main function on the tg_monitor_gui.py file.

If connectivity and functions want to be tested the bu_data_model.py can be tested by itself by running it stand alone
