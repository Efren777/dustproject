#!/usr/bin/python

#============================ adjust path =====================================

import sys
import os
if __name__ == "__main__":
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '..', '..','libs'))
    sys.path.insert(0, os.path.join(here, '..', '..','external_libs'))

#============================ verify installation =============================

from SmartMeshSDK.utils import SmsdkInstallVerifier
(goodToGo,reason) = SmsdkInstallVerifier.verifyComponents(
    [
        SmsdkInstallVerifier.PYTHON,
        SmsdkInstallVerifier.PYSERIAL,
    ]
)
if not goodToGo:
    print "Your installation does not allow this application to run:\n"
    print reason
    raw_input("Press any button to exit")
    sys.exit(1)

#============================ imports =========================================

import threading
import copy
import time
import traceback

from   SmartMeshSDK.utils              import AppUtils,                   \
                                              FormatUtils,                \
                                              LatencyCalculator
from   SmartMeshSDK.ApiDefinition      import IpMgrDefinition,            \
                                              HartMgrDefinition
from   SmartMeshSDK.IpMgrConnectorMux  import IpMgrSubscribe,             \
                                              IpMgrConnectorMux
from   SmartMeshSDK.ApiException       import APIError
from   SmartMeshSDK.protocols.oap      import OAPDispatcher,              \
                                              OAPClient,                  \
                                              OAPMessage,                 \
                                              OAPNotif
from   dustUI                          import dustWindow,                 \
                                              dustFrameApi,               \
                                              dustFrameConnection,        \
                                              dustFrameMoteList,          \
                                              dustFrameText,              \
                                              dustStyle


#============================ defines =========================================

GUI_UPDATEPERIOD = 250   # in ms

# columns names
COL_LED          = 'Led ON'
COL_LEDOFF       ='Led OFF'
COL_GETD0        ='Get D0'
COL_D0           ='DO'
COL_GETD1        ='Get D1'
COL_D1           ='D1'
COL_GETD2        ='Get D2'
COL_D2           ='D2'
COL_GETD3        ='Get D3'
COL_D3           ='D3'

#============================ body ============================================

##
# \addtogroup TempMonitor
# \{
# 

class notifClient(object):
    
    def __init__(self, apiDef, connector, disconnectedCallback, latencyCalculator):
        
        # store params
        self.apiDef               = apiDef
        self.connector            = connector
        self.disconnectedCallback = disconnectedCallback
        self.latencyCalculator    = latencyCalculator
        
        
        # variables
        self.dataLock             = threading.Lock()
        self.isMoteActive         = {}
        self.data                 = {}
        self.updates              = {}
        
        # subscriber

        self.subscriber = IpMgrSubscribe.IpMgrSubscribe(self.connector)
        self.subscriber.start()
        self.subscriber.subscribe(
                notifTypes =    [
                                    IpMgrSubscribe.IpMgrSubscribe.NOTIFDATA,
                                ],
                fun =           self._dataCallback,
                isRlbl =        False,
            )
        self.subscriber.subscribe(
                notifTypes =    [
                                    IpMgrSubscribe.IpMgrSubscribe.NOTIFEVENT,
                                ],
                fun =           self._eventCallback,
                isRlbl =        True,
            )
        self.subscriber.subscribe(
                notifTypes =    [
                                    IpMgrSubscribe.IpMgrSubscribe.ERROR,
                                    IpMgrSubscribe.IpMgrSubscribe.FINISH,
                                ],
                fun =           self.disconnectedCallback,
                isRlbl =        True,
            )
        
        # OAP dispatcher
        self.oap_dispatch = OAPDispatcher.OAPDispatcher()
        self.oap_dispatch.register_notif_handler(self._handle_oap_notif)
    
    #======================== public ==========================================
    
    def getData(self):
        self.dataLock.acquire()
        returnIsMoteActive   = copy.deepcopy(self.isMoteActive)
        returnData           = copy.deepcopy(self.data)
        returnUpdates        = copy.deepcopy(self.updates)
        self.updates         = {}
        
        self.dataLock.release()
        return (returnIsMoteActive,returnData,returnUpdates)
    
    def getOapDispatcher(self):
        return self.oap_dispatch
    
        
    def disconnect(self):
        self.connector.disconnect()
    
    #======================== private =========================================

    def _dataCallback(self,notifName,notifParams):

        timeNow =rime.time()

        mac=self._getMacFromNotifParams(notifParams)

        self.dataLock.acquire()
        
        if mac not in self.data:
            self.data[mac] = {}
        if notifName not in self.data[mac]:
            self.data[mac][notifName] = 0

        if mac not in self.updates:
            self.updates[mac] = []
        if notifName not in self.updates[mac]:
            self.updates[mac].append(notifName)

        self.dataLock.release()

    def _eventCallback(self,notifName,notifParams):
        
        self.dataLock.acquire()

        if notifName in [IpMgrSubscribe.IpMgrSubscribe.EVENTMOTEOPERATIONAL]:
                    mac = self._getMacFromNotifParams(notifParams)
                    self.isMoteActive[mac] = True
                    
        if notifName in [IpMgrSubscribe.IpMgrSubscribe.EVENTMOTELOST]:
                    mac = self._getMacFromNotifParams(notifParams)
                    self.isMoteActive[mac] = False
                    
        self.dataLock.release()
    
    def _getMacFromNotifParams(self,notifParams):
        
        if   isinstance(self.apiDef,IpMgrDefinition.IpMgrDefinition):
            # we are connected to an IP manager
            return tuple(notifParams.macAddress)
    
    def _handle_oap_notif(self,mac,notif):
        
        # convert MAC to tuple
        mac = tuple(mac)
        '''
        self.dataLock.acquire()
        
        if isinstance(notif,OAPNotif.OAPAnalogSample):
            print "analog sample:"
            print notif
            
        if isinstance(notif,OAPNotif.OAPAnalogStats):
            print "analog stats:"
            print notif
            
        if isinstance(notif,OAPNotif,OAPDigitalIn):
            self.dataLock.acquire()
            print "digitalin:"
            print notif
            
        
        
        if isinstance(notif,OAPNotif.OAPTempSample):
            # this is a temperature notification
            
            # lock the data structure
            # add mac/type to updates, if necessary
            if mac not in self.data:
                self.data[mac] = {}
            if COL_TEMPERATURE not in self.data[mac]:
                self.data[mac][COL_TEMPERATURE] = None
            if COL_TEMP_NUM not in self.data[mac]:
                self.data[mac][COL_TEMP_NUM]   = 0
            
            # add mac/type to updates, if necessary
            if mac not in self.updates:
                self.updates[mac] = []
            if COL_TEMPERATURE not in self.updates[mac]:
                self.updates[mac].append(COL_TEMPERATURE)
            if COL_TEMP_NUM not in self.updates[mac]:
                self.updates[mac].append(COL_TEMP_NUM)
            
            self.data[mac][COL_TEMPERATURE]  = notif.samples[0]
            self.data[mac][COL_TEMP_NUM]   += 1
            
            # unlock the data structure
        self.dataLock.release()
        '''

class TempMonitorGui(object):
    
    def __init__(self):
        
        # local variables
        self.guiLock            = threading.Lock()
        self.apiDef             = IpMgrDefinition.IpMgrDefinition()
        self.notifClientHandler = None
        self.latencyCalculator  = None
        self.guiUpdaters        = 0
        self.oap_clients        = {}
        
        # create window
        self.window = dustWindow.dustWindow('TempMonitor',
                                 self._windowCb_close)
        
                
        # add a connection frame
        self.connectionFrame = dustFrameConnection.dustFrameConnection(
                                    self.window,
                                    self.guiLock,
                                    self._connectionFrameCb_connected,
                                    frameName="manager connection",
                                    row=0,column=0)

        self.connectionFrame.apiLoaded(self.apiDef)
        self.connectionFrame.show()

        
        # add a mote list frame
        columnnames =       [
                                # led
                                {
                                    'name': COL_LED,
                                    'type': dustFrameMoteList.dustFrameMoteList.ACTION,
                                },
                                {
                                    'name': COL_LEDOFF,
                                    'type': dustFrameMoteList.dustFrameMoteList.ACTION,
                                },
                                #DIGITAL INPUT
                                {
                                    'name': COL_GETD0,
                                    'type': dustFrameMoteList.dustFrameMoteList.ACTION,
                                },
                                {
                                    'name': COL_D0,
                                    'type': dustFrameMoteList.dustFrameMoteList.LABEL,
                                },
                                {
                                    'name': COL_GETD1,
                                    'type': dustFrameMoteList.dustFrameMoteList.ACTION,
                                },
                                {
                                    'name': COL_D1,
                                    'type': dustFrameMoteList.dustFrameMoteList.LABEL,
                                },
                                {
                                    'name': COL_GETD2,
                                    'type': dustFrameMoteList.dustFrameMoteList.ACTION,
                                },
                                {
                                    'name': COL_D2,
                                    'type': dustFrameMoteList.dustFrameMoteList.LABEL,
                                },
                                {
                                    'name': COL_GETD3,
                                    'type': dustFrameMoteList.dustFrameMoteList.ACTION,
                                },
                                {
                                    'name': COL_D3,
                                    'type': dustFrameMoteList.dustFrameMoteList.LABEL,
                                },
                                
                            ]
        self.moteListFrame = dustFrameMoteList.dustFrameMoteList(self.window,
                                               self.guiLock,
                                               columnnames,
                                               row=1,column=0)
        self.moteListFrame.show()
        
        # add a status (text) frame
        self.statusFrame   = dustFrameText.dustFrameText(
                                    self.window,
                                    self.guiLock,
                                    frameName="status",
                                    row=2,column=0)
        self.statusFrame.show()
        
    #======================== public ==========================================
    
    def start(self):
        
        # start Tkinter's main thead
        try:
            self.window.mainloop()
        except SystemExit:
            sys.exit()

    #======================== private =========================================
    
    #===== user interaction
    
    
    
    def _connectionFrameCb_connected(self,connector):
        '''
        \brief Called when the connectionFrame has connected.
        '''
        
        # store the connector
        self.connector = connector
        
        # start a latency calculator
        self.latencyCalculator = LatencyCalculator.LatencyCalculator(self.apiDef,self.connector)
        self.latencyCalculator.start()
        
        # start a notification client
        self.notifClientHandler = notifClient(
                    self.apiDef,
                    self.connector,
                    self._connectionFrameCb_disconnected,
                    self.latencyCalculator,
                )
        
        # retrieve list of motes from manager
        macs = self._getOperationalMotesMacAddresses()
        for mac in macs:
            self._addNewMote(mac)
        
        # clear the colors on the GUI
        self.moteListFrame.clearColors()
        
        # schedule the GUI to update itself in GUI_UPDATEPERIOD ms
        if self.guiUpdaters==0:
            self.moteListFrame.after(GUI_UPDATEPERIOD,self._updateMoteList)
            self.guiUpdaters += 1
        
        # update status
        self.statusFrame.write("Connection to manager successful.")
    
    
        
    def _moteListFrameCb_Led(self,mac,button):
        
        self.oap_clients[mac].send( OAPMessage.CmdType.PUT,
                                    [3,2],
                                    data_tags=[ OAPMessage.TLVByte(t=0,v=1)],
                                    cb=None,
                                   )
        
        self.statusFrame.write("Set led on of mote {0}".format(FormatUtils.formatMacString(mac)))

    def _moteListFrameCb_Ledoff(self,mac,button):
        
        self.oap_clients[mac].send( OAPMessage.CmdType.PUT,
                                    [3,2],
                                    data_tags=[ OAPMessage.TLVByte(t=0,v=0)],
                                    cb=None,
                                   )
        
        self.statusFrame.write("Set led off of mote {0}".format(FormatUtils.formatMacString(mac)))
        

    def _moteListFrameCb_getd0(self,mac,button):
        
        self.oap_clients[mac].send( OAPMessage.CmdType.GET,
                                    [2,0],
                                    data_tags=None,
                                    cb=self._oap_getd0,
                                   )
        
        self.statusFrame.write("Get digital input 0 of mote {0}".format(FormatUtils.formatMacString(mac)))

    def _moteListFrameCb_getd1(self,mac,button):
        
        self.oap_clients[mac].send( OAPMessage.CmdType.GET,
                                    [2,1],
                                    data_tags=None,
                                    cb=self._oap_getd1,
                                   )
        
        self.statusFrame.write("Get digital input 1 of mote {0}".format(FormatUtils.formatMacString(mac)))

    def _moteListFrameCb_getd2(self,mac,button):
        
        self.oap_clients[mac].send( OAPMessage.CmdType.GET,
                                    [2,2],
                                    data_tags=None,
                                    cb=self._oap_getd2,
                                   )
        
        self.statusFrame.write("Get digital inpit 2 of mote {0}".format(FormatUtils.formatMacString(mac)))

    def _moteListFrameCb_getd3(self,mac,button):
        
        self.oap_clients[mac].send( OAPMessage.CmdType.GET,
                                    [2,3],
                                    data_tags=None,
                                    cb=self._oap_getd3,
                                   )
        
        self.statusFrame.write("Get digital input 3 of mote {0}".format(FormatUtils.formatMacString(mac)))
        

    
    def _connectionFrameCb_disconnected(self,notifName=None,notifParams=None):
        '''
        \brief Called when the connectionFrame has disconnected.
        '''
        
        # kill the latency calculator thread
        if self.latencyCalculator:
            self.latencyCalculator.disconnect()
            self.latencyCalculator = None
        
        # update the GUI
        self.connectionFrame.updateGuiDisconnected()
        
        # delete the connector
        self.connector = None
    
    def _windowCb_close(self):
        if self.latencyCalculator:
            self.latencyCalculator.disconnect()
        if self.notifClientHandler:
            self.notifClientHandler.disconnect()
    
    #===== helpers
    
    def _getOperationalMotesMacAddresses(self):
        returnVal = []
        
        if   isinstance(self.apiDef,IpMgrDefinition.IpMgrDefinition):
            # we are connected to an IP manager
            
            currentMac     = (0,0,0,0,0,0,0,0) # start getMoteConfig() iteration with the 0 MAC address
            continueAsking = True
            while continueAsking:
                try:
                    res = self.connector.dn_getMoteConfig(currentMac,True)
                except APIError:
                    continueAsking = False
                else:
                    if ((not res.isAP) and (res.state in [4,])):
                        returnVal.append(tuple(res.macAddress))
                    currentMac = res.macAddress
        
        
        else:
            output = "apiDef of type {0} unexpected".format(type(self.apiDef))
            print output
            raise SystemError(output)
        
        # order by increasing MAC address
        returnVal.sort()
        
        return returnVal
    
    def _addNewMote(self,mac):
    
        # add mote to GUI
        # Note: if you're reconnecting, mote already exists
        
        columnvals = {
            # led
            COL_LED:                {
                                        'text':     'ON',
                                        'callback': self._moteListFrameCb_Led,
                                    },
            COL_LEDOFF:             {
                                        'text':     'OFF',
                                        'callback': self._moteListFrameCb_Ledoff,
                                    },
            COL_GETD0:              {
                                        'text':     'GET',
                                        'callback': self._moteListFrameCb_getd0,
                                     },
            COL_GETD1:               {
                                        'text':     'GET',
                                        'callback': self._moteListFrameCb_getd1,
                                     },
            COL_GETD2:               {
                                        'text':     'GET',
                                        'callback': self._moteListFrameCb_getd2,
                                     },
            COL_GETD3:               {
                                        'text':     'GET',
                                        'callback': self._moteListFrameCb_getd3,
                                     },
            
            # counters and latency
            COL_D0:                    0,
            COL_D1:                    0,
            COL_D2:                    0,
            COL_D3:                    0,
            
        }
        
        if mac not in self.oap_clients:
            self.moteListFrame.addMote(
                    mac,
                    columnvals,
                )
        
        # create OAPClient
        # Note: if you're reconnecting, this recreates the OAP client
        self.oap_clients[mac] = OAPClient.OAPClient(mac,
                                                    self._sendDataToConnector,
                                                    self.notifClientHandler.getOapDispatcher())
    def _oap_getd0(self,mac,oap_resp):

        d0=OAPMessage.Temperature()
        d0.parse_response(oap_resp)
        self.moteListFrame.update(mac,COL_D0,d0.value)
        print d0.value
        
    def _oap_getd1(self,mac,oap_resp):
        
        d1=OAPMessage.Temperature()
        d1.parse_response(oap_resp)
        self.moteListFrame.update(mac,COL_D1,d1.value.value)
        
    def _oap_getd2(self,mac,oap_resp):

        d2=OAPMessage.Temperature()
        d2.parse_response(oap_resp)
        self.moteListFrame.update(mac,COL_D2,d2.value.value)
        
    def _oap_getd3(self,mac,oap_resp):

        d3=OAPMessage.Temperature()
        d3.parse_response(oap_resp)
        self.moteListFrame.update(mac,COL_D3,d3.value.value)
        
    
    def _updateMoteList(self):

        (isMoteActive,data,updates) = self.notifClientHandler.getData()
    
        
        # update the frame
        for mac,data in data.items():
            
            # detect new motes
            if mac not in self.oap_clients:
                self._addNewMote(mac)
            
                        
        
        # enable/disable motes
        for mac in isMoteActive:
            if isMoteActive[mac]:
                self.moteListFrame.enableMote(mac)
            else:
                self.moteListFrame.disableMote(mac)
        
        # schedule the next update
        self.moteListFrame.after(GUI_UPDATEPERIOD,self._updateMoteList)
    
    def _sendDataToConnector(self,mac,priority,srcPort,dstPort,options,data):

        
        if   isinstance(self.apiDef,IpMgrDefinition.IpMgrDefinition):
            # we are connected to an IP manager
            self.connector.dn_sendData(
                mac,
                priority,
                srcPort,
                dstPort,
                options,
                data
            )
        else:
            output = "apiDef of type {0} unexpected".format(type(self.apiDef))
            print output
            raise SystemError(output)

#============================ main ============================================

def main():
    TempMonitorGuiHandler = TempMonitorGui()
    TempMonitorGuiHandler.start()

if __name__ == '__main__':
    main()

##
# end of TempMonitor
# \}
# 
