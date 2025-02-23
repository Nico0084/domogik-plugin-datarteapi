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

- datarteapi Manager

"""

import traceback
import threading
import requests
import time
import locale
from datetime import datetime, timedelta
from dateutil import tz
import xml.etree.ElementTree as XmlET
import urllib
from six.moves.html_parser import HTMLParser
import zmq
from domogikmq.reqrep.client import MQSyncReq
from domogikmq.message import MQMessage
from domogik_packages.plugin_datarteapi.lib.datarteapi import BaseDataRteApi, RteApiBadRequest, RteApiServerError, RteApiUnexpectedError

# API_TEMPO_ENDPOINT = (
#     "https://{0}/open_api/tempo_like_supply_contract/v1/tempo_like_calendars".format(API_DOMAIN)
# )
API_REQ_TIMEOUT = 3
API_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
FRANCE_TZ = tz.gettz("Europe/Paris")
HEURE_CHANGEMENT = 6
API_KEY_ERROR = "error"
API_KEY_ERROR_DESC = "error_description"
API_KEY_RESULTS = "tempo_like_calendars"
API_KEY_VALUES = "values"
API_KEY_START = "start_date"
API_KEY_END = "end_date"
API_KEY_VALUE = "value"
API_KEY_UPDATED = "updated_date"
API_VALUE_RED = "RED"
API_VALUE_WHITE = "WHITE"
API_VALUE_BLUE = "BLUE"

TIME_CHECK = 3600

class DataRteTempo(BaseDataRteApi):
    """ DataRteSTempo
    """

    def __init__(self, manager, device, apitempoendpoint, idclient, idsecret):
        """ Init VigiRnsaPollens object
            @param log : log instance
            @param send : send
            @param stop : stop flag
            @param device : domogik device
            @param apitempoendpoint : URL Tempo service endpoint
            @param idclient : Rte id client
            @param idsecret : Rte id client
        """
        self.end_token = 0
        BaseDataRteApi.__init__(self, manager, device, idclient, idsecret)
        self.apitempoendpoint = apitempoendpoint
        self.currentday = self.getLastCurrentSensor('CurrentColor') 
        self.currentday = self.getCurrentColor()

    def setParams(self, dep):
        if self.dep != dep :
            self.log.info(u"Device {0} updated departement '{1}' to '{2}'".format(self.device['id'], self.dep, dep))
            self.dep = dep
            self._lastUpdate = 0

    def check(self):
        """ Requête data RTE pour obtenir la dernière valeur de couleur annoncée
        """
        self.run = True
        self._lastUpdate = 0
        self.log.info(u"Start to check last color day tempo Rte status '{0}'".format(self.device['name']))
        token = False if self.end_token == 0 else True
        try :
            while not self._stop.isSet() and self.run:
                dNow = datetime.now(FRANCE_TZ)
                dChange = dNow.replace(hour = HEURE_CHANGEMENT, minute = 0, second = 0)
                if time.time() >= self.end_token or not token:
                    token = self.loadToken()
                dt = (dNow - dChange).total_seconds()
                if 0 < dt <= 40 :
                    self.getCurrentColor()
                if token and self._lastUpdate + TIME_CHECK < time.time() :
                    self.log.debug(u"Get last day tempo Rte status for {0}".format(self.device["name"]))
                    status_code, data = self.requestRteData({'fallback_status' : 'false'})
                    if status_code == 200:
                        try :
                            for day in data['tempo_like_calendars']['values'] :
                                update_day = datetime.strptime(day['updated_date'][:-6], '%Y-%m-%dT%H:%M:%S').replace(tzinfo = FRANCE_TZ)
                                if update_day.date() == dNow.date() :
                                    date_start = day['start_date'][:-6]
                                    date_end = day['end_date'][:-6]
                                    dStart = datetime.strptime(date_start, '%Y-%m-%dT%H:%M:%S').replace(hour = HEURE_CHANGEMENT, tzinfo = FRANCE_TZ)
                                    dEnd = datetime.strptime(date_end, '%Y-%m-%dT%H:%M:%S').replace(hour = HEURE_CHANGEMENT, tzinfo = FRANCE_TZ)
                                    dbColorDay = self.getLastCurrentSensor('ColorDay')
                                    toSend = False
                                    if dbColorDay == day['value'] :
                                        dbStartDate = datetime.strptime(self.getLastCurrentSensor('StartDate')[:-2],'%Y-%m-%dT%H:%M:%S').replace(tzinfo = FRANCE_TZ)
                                        if dbStartDate != dStart:
                                            toSend = True
                                        else :
                                            dbEndDate = datetime.strptime(self.getLastCurrentSensor('EndDate')[:-2],'%Y-%m-%dT%H:%M:%S').replace(tzinfo = FRANCE_TZ)
                                            if dbEndDate != dEnd :
                                                toSend = True
                                    else : toSend = True
                                    if toSend :
                                        date_start = dStart.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5]
                                        date_end = dEnd.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5]
                                        self._send(self.device, {'StartDate': date_start,'EndDate': date_end, 'ColorDay': day['value']})
                            self._lastUpdate = time.time()
                        except :
                            self.log.error(u"Error getting day tempo Rte status for '{0}' : {1}".format(self.device['name'], traceback.format_exc()))
                    else:
                        self.log.warning(u"Error getting day tempo Rte status for ''{0}' error : {1}".format(self.device['name'], status_code))
                    self.log.info(u"Next day tempo Rte check for '{0}' at : {1}".format(self.device['name'], datetime.fromtimestamp(self._lastUpdate + TIME_CHECK)))
                self._stop.wait(30)
        except :
            self.log.error(u"Check tempo Rte device '{0}' error: {1}".format(self.device['name'], (traceback.format_exc())))
        self.run = False
        self.log.info(u"Stopped tempo Rte checking for '{0}'".format(self.device['name']))

    def getLastCurrentSensor(self, sensor):
        """ Retourne la dernière valeur du sensor connue"""
        sensor_id = self.manager.getSensorId(self.device['id'], sensor)
        value = None
        if sensor_id :
            cli = MQSyncReq(zmq.Context())
            msg = MQMessage()
            msg.set_action('sensor_history.get')
            msg.add_data('sensor_id', sensor_id)
            msg.add_data('mode', 'last')
            msg.add_data('number', 1)
            res = cli.request('admin', msg.get(), timeout=10)
            if res is not None :
                resData = res.get_data()
                if resData['values'] and resData['values'][0]['value_str'] is not None :
                    value = resData['values'][0]['value_str']
        return value

    def getCurrentColor(self):
        """ Requête data RTE et calcul la couleur courant d'aujourd'hui """
        dNow = datetime.now(FRANCE_TZ)
        date_start = datetime(dNow.year, dNow.month, dNow.day-1,0,0,0, tzinfo=FRANCE_TZ).strftime(API_DATE_FORMAT)
        date_end = datetime(dNow.year, dNow.month, dNow.day+1,23,59,0, tzinfo=FRANCE_TZ).strftime(API_DATE_FORMAT)
        params = {
            "start_date": date_start[:-2] + ":" + date_start[-2:],
            "end_date": date_end[:-2] + ":" + date_end[-2:],
            'fallback_status' : 'false'
        }
        self.log.info(u"Get current color of today from {0}".format(params))
        status_code, data = self.requestRteData(params)
        if status_code == 200:
            try :
                for day in data['tempo_like_calendars']['values'] :
                    date_start = day['start_date'][:-6]
                    date_end = day['end_date'][:-6]
                    dStart = datetime.strptime(date_start, '%Y-%m-%dT%H:%M:%S').replace(hour = HEURE_CHANGEMENT, tzinfo = FRANCE_TZ)
                    dEnd = datetime.strptime(date_end, '%Y-%m-%dT%H:%M:%S').replace(hour = HEURE_CHANGEMENT, tzinfo = FRANCE_TZ)
                    if  dStart <=  dNow and dEnd > dNow :
                        if self.currentday != day['value'] :
                            self.currentday = day['value']
                            self.log.info(u'{0} set currentday to {1}'.format(self.device['name'], self.currentday))
                            self._send(self.device, {'CurrentColor': self.currentday})
                        break
            except :
                self.log.error(u"Error getting data for '{0}' bad json decode : {1}, error {2}".format(self.device['name'], response.content, traceback.format_exc()))
                data = False
        else :
            self.log.error(u"Error getting data for '{0}' error : {1}: {2}".format(self.device['name'], response.status_code, response.content))
            data = False

        return status_code, data

    def requestRteData(self, params):
        url_rte_tempo = "https://{0}{1}".format(self._apidomaine, self.apitempoendpoint)
        headers = {'Authorization': '{0} {1}'.format(self.token_type, self.access_token),'Accept': 'application/json'}
        data = None
        try:
            response = requests.get(url_rte_tempo, headers=headers, params=params)
            self.handleApiErrors(response)
        except requests.exceptions.RequestException as requests_exception:
            self.log.error(u"API request failed: {0}".format(requests_exception))
            return response.status_code, None
        except (RteApiBadRequest, RteApiServerError, RteApiUnexpectedError) as http_error:
            self.log.error("API request failed with HTTP error code: {0}".format(http_error))
            return response.status_code, None
        if response.status_code == 200:
            try :
                data = response.json()
            except :
                self.log.error(u"Error getting day tempo Rte status for '{0}' bad json format : {1}, error {2}".format(self.device['name'], response.content, traceback.format_exc()))
                return 500, data
        else:
            self.log.error(u"Error getting day tempo Rte status for '{0}' error : {1}: {2}".format(self.device['name']), response.status_code, response.content)
        return response.status_code, data
    