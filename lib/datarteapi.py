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

- datarteapi base class

"""

import time
import requests

RTE_ERROR_API = {
    "TMPLIKSUPCON_TMPLIKCAL_F01" : u"Cette erreur est générée si les paramètres start_date et end_date sont passés l’un sans l’autre.",
    "TMPLIKSUPCON_TMPLIKCAL_F02" : u"Cette erreur est générée si le paramètre start_date est plus récent que le paramètre end_date.",
    "TMPLIKSUPCON_TMPLIKCAL_F03" : u"Cette erreur est générée si la période demandée est supérieure à 366 jours.",
    "TMPLIKSUPCON_TMPLIKCAL_F04" : u"Cette erreur est générée si end_date est supérieur à J+2 par rapport à la date système.",
    "TMPLIKSUPCON_TMPLIKCAL_F05" : u"Cette erreur est générée si l’intervalle de temps entre start_date et end_date est inférieur 1 jour calendaire.",
    "TMPLIKSUPCON_TMPLIKCAL_F06" : u"Cette erreur est générée si au moins un des paramètres start_date ou end_date n’a pas le format attendu.",
    "TMPLIKSUPCON_TMPLIKCAL_F07" : u"Cette erreur est générée si le champ fallback_status n’a pas la valeur true ou false.",
    "401" : u"Erreur générée lorsque l’authentification a échouée.",
    "403" : u"Erreur générée si l’appelant n’est pas habilité à appeler la ressource.",
    "404" : u"La ressource appelée n’existe pas ou aucune page n’a été trouvée.",
    "408" : u"Erreur générée sur non réponse du service appelé ou retour en timeout (http 408) du service appelé.",
    "413" : u"La taille de la réponse de la requête dépasse 7Mo",
    "414" : u"L’URI transmise par l’appelant dépasse 2048 caractères.",
    "429" : u"Le nombre d’appel maximum dans un certain laps de temps est dépassé.",
    "500" : u"Toute autre erreur technique.(Cette erreur est accompagnée d’un message JSON avec un champ error_code et error_description)",
    "503" : u"Erreur générée sur maintenance (http 503).",
    "509" : u"L‘ensemble des requêtes des clients atteint la limite maximale.",
    }

class DataRteApiException(Exception):
    """
    datarteapi exception
    """
    def __init__(self, value):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return repr(self.value)
    

class RteApiBadRequest(DataRteApiException):
    """Représente une erreur HTTP 4xx."""
    def __init__(self, code, erreur=None):
        """Initialise BadRequest exception."""
        DataRteApiException.__init__(self, code)
        self.erreur = erreur

    def __str__(self):
        if self.value == 400 :
            msg = u"Erreur <{0}> : {1}".format(self.erreur['error_code'], self.erreur['error_description'])
        else :
            msg = RTE_ERROR_API["{0}".format(self.value)]
        return repr(u"HTTP code {0} : {1}".format(self.value, msg))


class RteApiServerError(DataRteApiException):
    """Représente une erreur HTTP 5xx."""
    def __init__(self, code, erreur=None):
        """Initialise ServerError exception."""
        DataRteApiException.__init__(self, code)
        self.erreur = erreur      
       
    def __str__(self):
        if self.value == 500 :
            msg = u"Erreur <{0}> : {1} \n URI aide : {2}\n Transaction : {3}".format(self.erreur['error_code'], self.erreur['error_description'], self.erreur['error_uri'], self.erreur['error_details']['transaction_id'])
        else :
            msg = RTE_ERROR_API["{0}".format(self.value)]
        return repr(u"HTTP code {0} : {1}".format(self.value, msg))

class RteApiUnexpectedError(DataRteApiException):
    """Représente un autre erreur HTTP non décrite dans la documentation de l'API."""

    def __init__(self, code, erreur=''):
        """Initialise UnexpectedError exception."""
        super(RteApiUnexpectedError, self).__init__(code)
        self.erreur = erreur      

    def __str__(self):
        return repr(u"HTTP code {0} : {1}".format(self.value, self.erreur))

class BaseDataRteApi:
    """ Base class of DataRteApi
    """

    def __init__(self, manager, device, idclient, idsecret):
        """ Init DataRteApi object
            @param log : log instance
            @param send : send
            @param stop : stop flag
            @param device : domogik device
        """
        self.manager = manager
        self.log = manager.log
        self.device = device
        self.idclient = idclient
        self.idsecret = idsecret
        self._send = manager.send_data
        self._stop = manager.get_stop()
        self.run = False
        self._lastUpdate = 0
        self.end_token = 0
        self._apidomaine = self.manager.get_config("apidomaine")
        self.loadToken()

    # -------------------------------------------------------------------------------------------------
    def setParams(self, params):
        """ Set params of type
            must be overwriten
        """
        self.log.warning(u"setParams function not implemented for base class DataRteApi")

    def check(self):
        """ Get DataRteApi datas
            must be overwriten
        """
        self.run = False
        self._lastUpdate = 0
        self.log.warning(u"Check function not implemented for base class DataRteApi")

    def loadToken(self):
        """ Connection au server via OAuth 2.0 (Open Authorization) et optention d’un jeton d’accès (token).
        """
        r = requests.post("https://{0}{1}".format(self._apidomaine, self.manager.get_config("apitokenendpoint")), auth=(self.idclient, self.idsecret))
        if r.ok :
            token = r.json()
            self.end_token = time.time() + token['expires_in']
            self.log.info(u"OAuth 2 Token loaded for device '{0}' for {1} s".format(self.device['name'], token['expires_in']))
            self.token_type = token['token_type']
            self.access_token = token['access_token']
            loaded = True
        else :
            loaded = False
            self.log.error(u"Loading Token fail with code {0} : {1}".format(r.status_code, RTE_ERROR_API["{0}".format(r.status_code)]))
        return loaded
    
    def handleApiErrors(self, response):
        """Gère les éventuelle erreur de retour de l'API."""
        if response.status_code == 400:
            try:
                data = response.json()
                raise RteApiBadRequest(response.status_code, data)
            except requests.exceptions.JSONDecodeError as exc:
                raise RteApiUnexpectedError(response.status_code, u"Failed to decode JSON API error: {0}".format(response.text))# from exc $$python3$$
            except KeyError as exc:
                raise RteApiUnexpectedError(response.status_code, u"Failed to decode JSON API error: {0}".format(response.text))# from exc $$python3$$
        elif response.status_code in [401, 403, 404, 408, 413, 414, 429] :
            raise RteApiBadRequest(response.status_code)
        elif response.status_code == 500:
            try:
                data = response.json()
                raise RteApiServerError(response.status_code, data)
            except : #requests.exceptions.JSONDecodeError as exc:
                raise RteApiUnexpectedError(response.status_code, u"Failed to decode JSON API error: {0}".format(response.text))# from exc $$python3$$
            # except KeyError as exc:
            #     raise RteApiUnexpectedError(response.status_code, u"Failed to decode JSON API error: {0}".format(response.text))# from exc $$python3$$
        elif response.status_code in [503, 509]:
            raise RteApiServerError(response.status_code)
        elif response.status_code != 200:
            raise RteApiUnexpectedError(response.status_code, u"Unexpected HTTP code: {0}".format(response.text))
