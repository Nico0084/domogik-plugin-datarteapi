#!/usr/bin/python
# -*- coding: utf-8 -*-

""" This file is part of B{Domogik} project (U{http://www.domogik.org}).

License
=======

B{Domogik} is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

B{Domogik} is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Domogik. If not, see U{http://www.gnu.org/licenses}.

Plugin purpose
==============

datarteapi

Implements
==========

- DataRteApiManager

"""

from domogik.common.plugin import Plugin
from domogik_packages.plugin_datarteapi.lib.datarteservices import DataRteTempo
import threading
import traceback

class DataRteApiManager(Plugin):
    """ Get datarteapi
    """

    def __init__(self):
        """ Init plugin
        """
        Plugin.__init__(self, name='datarteapi')

        # check if the plugin is configured. If not, this will stop the plugin and log an error
        #if not self.check_configured():
        #    return
        # get the devices list
        self.devices = self.get_device_list(quit_if_no_device = True)

        # get the sensors id per device :
        self.sensors = self.get_sensors(self.devices)

        # create a DataRteApi thread for each device
        self.datarteapithreads = {}
        self.datarteapi_list = {}
        self._loadDMGDevices()
        # Callback for new/update devices
        self.log.info(u"==> Add callback for new/update devices.")
        self.register_cb_update_devices(self.reload_devices)
        self.ready()

    def _loadDMGDevices(self):
        """ Check and load domogik device if necessary
        """
        datarteapi_list = {}
        directory = "{0}/{1}_{2}".format(self.get_packages_directory(), self._type, self._name)
        for a_device in self.devices: # for now, only datarteapi.tempo device type, to add other add an handling device_type
            try:
                # global device parameters
                apitempoendpoint = self.get_parameter(a_device, "apitempoendpoint")
                idclient = self.get_parameter(a_device, "idclient")
                idsecret = self.get_parameter(a_device, "idsecret")
                if idclient != "" and idsecret != "":
                    device_id = a_device["id"]
                    if device_id not in self.datarteapi_list :
                        self.log.info(u"Create device ({0}) RTE Tempo for client '{1}'".format(device_id, idclient))
                        datarteapi_list[device_id] = DataRteTempo(self, a_device, apitempoendpoint, idclient, idsecret)
                        # start the RTE token thread
                        thr_name = "rtetoken_{0}".format(device_id)
                        self.datarteapithreads[thr_name] = threading.Thread(None,
                                                  datarteapi_list[device_id].check,
                                                  thr_name,
                                                  (),
                                                  {})
                        self.datarteapithreads[thr_name].start()
                        self.register_thread(self.datarteapithreads[thr_name])
                    else :
                        self.datarteapi_list[device_id].setParams(idclient)
                        datarteapi_list[device_id] = self.datarteapi_list[device_id]
                else:
                    self.log.error(u"### Device {0} not created, idclient '{1}' and/or idsecret '{2} not set !".format(a_device["name"], idclient, idsecret))
            except:
                self.log.error(u"{0}".format(traceback.format_exc()))   # we don't quit plugin if an error occured, a rte data token device can be KO and the others be ok
        # Check deleted devices
        for device_id in self.datarteapi_list :
            if device_id not in datarteapi_list :
                thr_name = "rtetoken_{0}".format(device_id)
                if thr_name in self.datarteapithreads :
                    self.run = False
                    self.unregister_thread(self.datarteapithreads[thr_name])
                    del self.datarteapithreads[thr_name]
                    self.log.info(u"Device {0} removed".format(device_id))

        self.datarteapi_list = datarteapi_list

    def getSensorId(self, device_id, sensor_name):
        """ get sensor id of a dmgdevice
        """
        if sensor_name in self.sensors[device_id] :
            return self.sensors[device_id][sensor_name]
        return False

    def send_data(self, device, dataSensors):
        """ Send data sensors values over MQ
        """
        data = {}
        for sensor, value in dataSensors.iteritems():
            if sensor in self.sensors[device['id']] :
                data[self.sensors[device['id']][sensor]] = value
        self.log.info(u"==> 0MQ PUB for {0} (id={1}) sended = {2} " .format(device['name'], device['id'], format(data)))
        try:
            self._pub.send_event('client.sensor', data)
        except:
            self.log.debug(u"Bad MQ message to send : {0}".format(data))
            pass

    def reload_devices(self, devices):
        """ Called when some devices are added/deleted/updated
        """
        self.devices = devices
        self.sensors = self.get_sensors(devices)
        self._loadDMGDevices()
        self.log.info(u"==> Reload Device called, All updated")

if __name__ == "__main__":
    datarteapi = DataRteApiManager()
