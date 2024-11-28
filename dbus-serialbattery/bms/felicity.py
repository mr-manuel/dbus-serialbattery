# -*- coding: utf-8 -*-
from battery import Battery, Cell
from utils import read_serial_data, unpack_from, logger
import utils
from struct import unpack
import struct
import sys


class Felicity(Battery):
    def __init__(self, port, baud, address):
        super(Felicity, self).__init__(port, baud, address)
        self.type = self.BATTERYTYPE

        # should be 0x01
        self.command_address = address

    BATTERYTYPE = "Felicity"
    LENGTH_CHECK = 4
    LENGTH_POS = 2
    
    # command bytes [Address field][Function code (03 = Read register)]
    #                   [Register Address (2 bytes)][Data Length (2 bytes)][CRC (2 bytes little endian)]
    
    command_read = b"\x03"
    command_cell_voltages = b"\x13\x2a\x00\x11"  # Registers 4906	
    command_bms_temp1_3 = b"\x13\x39\x00\x05"  # Register  4929-4931 (tempsensor1-3) 
    
    command_dvcc = b"\x13\x1C\x00\x04"  # Registers  4892(charger and discharger informations)
     
    command_status = b"\x13\x02\x00\x01"  # Registers 4866(battery status)
    command_fault = b"\x13\x04\x00\x01"  # Registers 4868(fault informations)
    
    command_total_voltage = b"\x13\x06\x00\x01"  # Register 4870
    command_current = b"\x13\x07\x00\x01"  # Register  4871 (signed int)
    command_bms_temp1 = b"\x13\x0A\x00\x01"  # Register  4874 (bms_temp)	
    command_soc = b"\x13\x0B\x00\x01"  # Registers 4875(soc)
    command_firmware_version = b"\xF8\x0B\x00\x01"  # Registers 63499 (1 byte string)
    command_serialnumber = b"\xF8\x04\x00\x05"  # Registers 63492 (1 byte string)

    # BMS warning and protection config

    def unique_identifier(self) -> str:
        return self.serial_number

    def test_connection(self):
        # call a function that will connect to the battery, send a command and retrieve the result.
        # The result or call should be unique to this BMS. Battery name or version, etc.
        # Return True if success, False for failure
        result = False
        try:
            result = self.read_gen_data() 
            result = result and self.get_settings()
            # get first data to show in startup log
            result = result and self.refresh_data()
        except Exception:
            (
                exception_type,
                exception_object,
                exception_traceback,
            ) = sys.exc_info()
            file = exception_traceback.tb_frame.f_code.co_filename
            line = exception_traceback.tb_lineno
            logger.error(
                f"Exception occurred: {repr(exception_object)} of type {exception_type} in {file} line #{line}"
            )
            result = False

        return result

    def get_settings(self):
        # After successful  connection get_settings will be call to set up the battery.
        # Set the current limits, populate cell count, etc
        # Return True if success, False for failure
        
        self.capacity = utils.BATTERY_CAPACITY if not None else 0.0
        self.max_battery_charge_current = utils.MAX_BATTERY_CHARGE_CURRENT
        self.max_battery_discharge_current = utils.MAX_BATTERY_DISCHARGE_CURRENT
        self.max_battery_voltage = utils.MAX_CELL_VOLTAGE * self.cell_count
        self.min_battery_voltage = utils.MIN_CELL_VOLTAGE * self.cell_count
        
        return True

    def refresh_data(self):
        # call all functions that will refresh the battery data.
        # This will be called for every iteration (1 second)
        # Return True if success, False for failure
        result = self.read_soc_data()
        result = result and self.read_cell_data()
        result = result and self.read_temp_data()

        return result

    def read_gen_data(self):

        firmware = self.read_serial_data_felicity(self.command_firmware_version)

        if firmware is False:
             return False

        self.version = str(unpack(">h", firmware)[0])
        logger.debug(">>> INFO: Battery Firmware: %s", self.version)
                
        
        serialnumber = self.read_serial_data_felicity(self.command_serialnumber)

        if serialnumber is False:
             return False

        s1 = str(unpack_from(">H",serialnumber, 0 * 2)[0])
        s2 = str(unpack_from(">H",serialnumber, 1 * 2)[0])
        s3 = str(unpack_from(">H",serialnumber, 2 * 2)[0])	
        s4 = str(unpack_from(">H",serialnumber, 3 * 2)[0])
        s5 = str(unpack_from(">H",serialnumber, 4 * 2)[0])

        self.serial_number = s1 + s2 + s3 + s4 + s5;

        logger.debug(">>> INFO: Battery Serialnumber: %s", self.serial_number)

        self.cell_count = 16
        for c in range(self.cell_count):
            self.cells.append(Cell(False))

        self.temp_sensors = 4

        return True

    def read_soc_data(self):

        soc_data = self.read_serial_data_felicity(self.command_soc)
        if soc_data is False:
              return False

        self.soc = unpack_from(">H", soc_data)[0]	
        logger.debug(">>> INFO: Battery SoC: %s", self.soc)


        voltage_data = self.read_serial_data_felicity(self.command_total_voltage)
        if voltage_data is False:
               return False

        self.voltage = unpack_from(">H", voltage_data)[0] / 100				
        logger.debug(">>> INFO: Battery voltage: %f V", self.voltage)

        current_data = self.read_serial_data_felicity(self.command_current)
        if current_data is False:
               return False

        self.current = unpack_from(">h", current_data)[0] / 10 * -1
        logger.debug(">>> INFO: Battery current: %f A", self.current)

        if utils.FELICITY_USE_BMS_VALUES is True:
              dvcc_data = self.read_serial_data_felicity(self.command_dvcc)
              if dvcc_data is False:
                    return False

              self.max_battery_voltage = unpack_from(">H", dvcc_data, 0 * 2)[0] / 100
              self.min_battery_voltage = unpack_from(">H", dvcc_data, 1 * 2)[0] / 100
              self.max_battery_charge_current = unpack_from(">H", dvcc_data, 2 * 2)[0] / 10
              self.max_battery_discharge_current = unpack_from(">H", dvcc_data, 3 * 2)[0] / 10

              logger.debug(">>> INFO: Max Battery voltage: %f V", self.max_battery_voltage)
              logger.debug(">>> INFO: Min Battery voltage: %f V", self.min_battery_voltage)
              logger.debug(">>> INFO: Max Battery charge current: %f A", self.max_battery_charge_current)
              logger.debug(">>> INFO: Max Battery discharge current: %f A", self.max_battery_discharge_current)

        status_data = self.read_serial_data_felicity(self.command_status)
        if status_data is False:
              return False

        status_int = unpack(">H",status_data)[0]

        # Charge enable
        self.charge_fet = True if (status_int & 0b0000000000000001) > 0 else False
        # Discharge enable
        self.discharge_fet = True if (status_int & 0b0000000000000100) > 0 else False

        logger.debug(">>> INFO: Battery Status: %f", status_int)	


        fault_data = self.read_serial_data_felicity(self.command_fault)
        if fault_data is False:
               return False

        fault_int = unpack(">H",fault_data)[0]

        logger.debug(">>> INFO: Battery Fault: %f", fault_int)		

        # Cell voltage high status
        #self.protection. = 2 if (fault_int & 0b0000000000000100) > 0 else 0
        # Cell voltage low status
        self.protection.voltage_cell_low = 2 if (fault_int & 0b0000000000001000) > 0 else 0
        # Charge current high status
        self.protection.current_over = 2 if (fault_int & 0b0000000000010000) > 0 else 0
        # Discharge current high status
        self.protection.current_under = 2 if (fault_int & 0b0000000000100000) > 0 else 0
        # BMS Temperature high status
        self.protection.temp_high_internal = 2 if (fault_int & 0b0000000001000000) > 0 else 0						
        # Cell Temperature high status
        self.protection.temp_high_charge = 2 if (fault_int & 0b0000000100000000) > 0 else 0
        # Cell Temperature low status
        self.protection.temp_low_charge = 2 if (fault_int & 0b0000001000000000) > 0 else 0
        
        return True

    def read_cell_data(self):
        cell_volt_data = self.read_serial_data_felicity(self.command_cell_voltages)
        for c in range(self.cell_count):
            try:
                cell_volts = unpack_from(">H", cell_volt_data, c * 2)
                if len(cell_volts) != 0:
                     self.cells[c].voltage = cell_volts[0] / 1000
            except struct.error:
                self.cells[c].voltage = 0
        return True

    def read_temp_data(self):
        tempBms = self.read_serial_data_felicity(self.command_bms_temp1)

        if tempBms is False:
            return False

        self.temp_mos = unpack(">h", tempBms)[0]

        temp1_3 = self.read_serial_data_felicity(self.command_bms_temp1_3)	

        if temp1_3 is False:
            return False

        self.temp1 = unpack_from(">h", temp1_3, 1 * 2)[0]
        self.temp2 = unpack_from(">h", temp1_3, 2 * 2)[0] 
        self.temp3 = unpack_from(">h", temp1_3, 3 * 2)[0] 

        logger.debug(">>> INFO: Battery TempMos: %f C", self.temp_mos)
        logger.debug(">>> INFO: Battery Temp1: %f C", self.temp1)		
        logger.debug(">>> INFO: Battery Temp2: %f C", self.temp2)	
        logger.debug(">>> INFO: Battery Temp3: %f C", self.temp3)	

        return True

    def read_bms_config(self):
        return True

    def calc_crc(self, data):
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for i in range(8):
                if (crc & 1) != 0:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return struct.pack("<H", crc)

    def generate_command(self, command):
        buffer = bytearray(self.command_address)
        buffer += self.command_read
        buffer += command
        buffer += self.calc_crc(buffer)

        return buffer

    def read_serial_data_felicity(self, command):
        # use the read_serial_data() function to read the data and then do BMS spesific checks (crc, start bytes, etc)
        data = read_serial_data(
            self.generate_command(command),
            self.port,
            self.baud_rate,
            self.LENGTH_POS,
            self.LENGTH_CHECK
        )
        #logger.debug(">>> INFO: Query: %s",self.generate_command(command))
        #logger.debug(">>> INFO: Result: %s", data)
        if data is False:
            return False

        start, flag, length = unpack_from("BBB", data)
        # checksum = unpack_from(">H", data, length + 3)
        #logger.debug(">>> INFO: Result: %s", data[3 : length + 3]) 

        if flag == 3:
            return data[3 : length + 3]
        else:
            logger.error(">>> ERROR: Felicity Incorrect Reply")
            return False
