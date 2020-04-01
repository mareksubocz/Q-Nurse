import xml.etree.ElementTree as ET
import os
file_name = "Instance1.ros"
full_file = os.path.abspath(os.path.join('instances1_24', file_name))

data = ET.parse(full_file)
contracts = data.find('StartDate')
print(type(contracts.text))
# pprint(list(map(lambda x: x., contracts.findall('Contract'))))
