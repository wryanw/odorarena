#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jul 23 10:26:20 2019

@author: bioelectrics
"""
import PySpin
from math import floor
# import os
import sys, linecache
from multiprocessing import Process
from queue import Empty
import multiCam_utils as multiCam
import time
from PIL import Image
import numpy as np
import pickle
import serial

class Run_Cams(Process):
    def __init__(self, camq, camq_p2read, array, frmGrab, camID, idList, cpt, bs, aq, frm, com):
        super().__init__()
        self.camID = camID
        self.camq = camq
        self.camq_p2read = camq_p2read
        self.array = array
        self.frmGrab = frmGrab
        self.idList = idList
        self.frmDims = cpt
        self.bs = bs
        self.aq = aq
        self.frm = frm
        self.com = com
        
    def run(self):
        # print('child: ',os.getpid())
        benchmark = False
        record = False
        ismaster = False
        record_frame_rate = 30
        aqW = self.frmDims[3]
        aqH = self.frmDims[1]
        user_cfg = multiCam.read_config()
        key_list = list()
        for cat in user_cfg.keys():
            key_list.append(cat)
        camStrList = list()
        for key in key_list:
            if 'cam' in key:
                camStrList.append(key)
        for s in camStrList:
            if self.camID == str(user_cfg[s]['serial']):
                camStr = s
        iscom = False
        isstim = False
        if user_cfg['stimAxes'] == camStr:
            isstim = True
        if user_cfg['axesRef'] == camStr:
            try:
                ser = serial.Serial(user_cfg['COM'], baudrate=115200)
                ser_success = True
                iscom = True
                self.com.value = 0
            except:
                ser_success = False
                self.com.value = -1
                print('\n ---Failed to connect to Arduino--- \n')
                
                
        while True:
            try:
                if iscom:
                    if self.com.value == 1:
                        ser.write(b'P')
                    elif self.com.value == 2:
                        ser.write(b'R')
                    elif self.com.value == 3:
                        ser.write(b'S')
                    elif self.com.value == 4:
                        ser.write(b'F')
                    self.com.value = 0
                    
                msg = self.camq.get(block=False)
#                print(msg)
                try:
                        
                    if msg == 'InitM':
                        ismaster = True
                        system = PySpin.System.GetInstance()
                        cam_list = system.GetCameras()
                        cam = cam_list.GetBySerial(self.camID)
                        cam.Init()
                        cam.CounterSelector.SetValue(PySpin.CounterSelector_Counter0)
                        cam.CounterEventSource.SetValue(PySpin.CounterEventSource_ExposureStart)
                        cam.CounterEventActivation.SetValue(PySpin.CounterEventActivation_RisingEdge)
                        cam.CounterTriggerSource.SetValue(PySpin.CounterTriggerSource_ExposureStart)
                        cam.CounterTriggerActivation.SetValue(PySpin.CounterTriggerActivation_RisingEdge)
                        cam.LineSelector.SetValue(PySpin.LineSelector_Line2)
                        cam.V3_3Enable.SetValue(True)
                        cam.LineSelector.SetValue(PySpin.LineSelector_Line1)
                        cam.LineSource.SetValue(PySpin.LineSource_Counter0Active)
                        cam.LineInverter.SetValue(False)
                        cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)
                        cam.TriggerSource.SetValue(PySpin.TriggerSource_Software)
                        cam.TriggerOverlap.SetValue(PySpin.TriggerOverlap_Off)
                        cam.TriggerMode.SetValue(PySpin.TriggerMode_On)
                        self.camq_p2read.put('done')
                    elif msg == 'InitS':
                        system = PySpin.System.GetInstance()
                        cam_list = system.GetCameras()
                        cam = cam_list.GetBySerial(self.camID)
                        cam.Init()
                        cam.TriggerSource.SetValue(PySpin.TriggerSource_Line3)
                        cam.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut)
                        cam.TriggerActivation.SetValue(PySpin.TriggerActivation_AnyEdge)
                        cam.TriggerMode.SetValue(PySpin.TriggerMode_On)
                        self.camq_p2read.put('done')
                    elif msg == 'Release':
                        cam.DeInit()
                        del cam
                        for i in self.idList:
                            cam_list.RemoveBySerial(str(i))
                        system.ReleaseInstance() # Release instance
                        if iscom:
                            if ser_success:
                                ser.close()
                            
                        self.camq_p2read.put('done')
                    elif msg == 'recordPrep':
                        path_base = self.camq.get()
                        write_frame_rate = 30
                        s_node_map = cam.GetTLStreamNodeMap()
                        handling_mode = PySpin.CEnumerationPtr(s_node_map.GetNode('StreamBufferHandlingMode'))
                        if not PySpin.IsAvailable(handling_mode) or not PySpin.IsWritable(handling_mode):
                            print('Unable to set Buffer Handling mode (node retrieval). Aborting...\n')
                            return
                        handling_mode_entry = handling_mode.GetEntryByName('OldestFirst')
                        handling_mode.SetIntValue(handling_mode_entry.GetValue())
                        
                        if not isstim:
                            avi = PySpin.SpinVideo()
                            option = PySpin.AVIOption()
                            option.frameRate = write_frame_rate
    #                        option = PySpin.MJPGOption()
    #                        option.frameRate = write_frame_rate
    #                        option.quality = 75
                        
                            print(path_base)
                            avi.Open(path_base, option)
                            
                        f = open('%s_timestamps.txt' % path_base, 'w')
                        start_time = 0
                        capture_duration = 0
                        record = True
                        self.camq_p2read.put('done')
                    elif msg == 'Start':
                        cam.BeginAcquisition()
                        if ismaster:
                            cam.LineSelector.SetValue(PySpin.LineSelector_Line1)
                            cam.LineSource.SetValue(PySpin.LineSource_Counter0Active)
                            self.frm.value = 0
                            self.camq.get()
                            cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)
                        
                        
                        if benchmark:
                            bA = 0
                            bB = 0
                            pre = time.perf_counter()
                        while self.aq.value > 0:
                            
                            image_result = cam.GetNextImage()
                            image_result = image_result.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
                            
                            if record:
                                if start_time == 0:
                                    start_time = image_result.GetTimeStamp()
                                else:
                                    capture_duration = image_result.GetTimeStamp()-start_time
                                    f.write("%s\n" % round(capture_duration))
                                    start_time = image_result.GetTimeStamp()
                                    # capture_duration = capture_duration/1000/1000
                                    frame = image_result.GetNDArray()
                                    
                                    if not isstim:
                                        avi.Append(image_result)
                                    else:
                                        frame = image_result.GetNDArray()
                                    
                            if not isstim and self.frmGrab.value == 0 and self.aq.value == 1:
                                frame = image_result.GetNDArray()
                                frame = np.array(Image.fromarray(frame).resize(size=(aqW,aqH)))
                                self.array[0:aqH*aqW] = frame.flatten()
                                self.frmGrab.value = 1
                            
                            if iscom:
                                if self.com.value == 1:
                                    ser.write(b'P')
                                elif self.com.value == 2:
                                    ser.write(b'R')
                                elif self.com.value == 3:
                                    ser.write(b'S')
                                elif self.com.value == 4:
                                    ser.write(b'F')
                                self.com.value = 0
                                
                            if ismaster:
                                self.frm.value+=1
                                
                            if benchmark:
                                bA+=1
                                bB+=time.perf_counter()-pre
                                pre = time.perf_counter()
                            
                        self.camq.get()
                        
                        if record:
                            if not isstim:
                                avi.Close()
                            f.close()
                            record = False
                            if benchmark:
                                was = round(bB/bA*1000*1000)
                                tried = round(1/record_frame_rate*1000*1000)
                                print(user_cfg[camStr]['nickname'] + ' actual: ' + str(was) + ' - target: ' + str(tried))
                                
                                
                        cam.EndAcquisition()
                        cam.TriggerMode.SetValue(PySpin.TriggerMode_On)
                        self.frmGrab.value = 0
                        if ismaster:
                            cam.LineSelector.SetValue(PySpin.LineSelector_Line1)
                            cam.LineSource.SetValue(PySpin.LineSource_FrameTriggerWait)
                            cam.LineInverter.SetValue(True)
                            
                        self.camq_p2read.put('done')
                    
        
                    elif msg == 'updateSettings':
                        user_cfg = multiCam.read_config()
                                
                        nodemap = cam.GetNodeMap()
                        binsize = user_cfg[camStr]['bin']
                        cam.BinningHorizontal.SetValue(int(binsize))
                        cam.BinningVertical.SetValue(int(binsize))

                        node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
                        if not PySpin.IsAvailable(node_acquisition_mode) or not PySpin.IsWritable(node_acquisition_mode):
                            print('Unable to set acquisition mode to continuous (enum retrieval). Aborting...')
                            return False
                        # Retrieve entry node from enumeration node
                        node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
                        if not PySpin.IsAvailable(node_acquisition_mode_continuous) or not PySpin.IsReadable(
                                node_acquisition_mode_continuous):
                            print('Unable to set acquisition mode to continuous (entry retrieval). Aborting...')
                            return False
                        acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()
                        # Set integer value from entry node as new value of enumeration node
                        node_acquisition_mode.SetIntValue(acquisition_mode_continuous)
                        # Retrieve the enumeration node from the nodemap
                        node_pixel_format = PySpin.CEnumerationPtr(nodemap.GetNode('PixelFormat'))
                        if PySpin.IsAvailable(node_pixel_format) and PySpin.IsWritable(node_pixel_format):
# =============================================================================
#                             # Retrieve the desired entry node from the enumeration node
#                             node_pixel_format_mono8 = PySpin.CEnumEntryPtr(node_pixel_format.GetEntryByName('Mono8'))
#                             if PySpin.IsAvailable(node_pixel_format_mono8) and PySpin.IsReadable(node_pixel_format_mono8):
#                                 # Retrieve the integer value from the entry node
#                                 pixel_format_mono8 = node_pixel_format_mono8.GetValue()
#                                 # Set integer as new value for enumeration node
#                                 node_pixel_format.SetIntValue(pixel_format_mono8)
#                             else:
#                                 print('Pixel format mono 8 not available...')
# =============================================================================
                            node_pixel_format_BayerRG8 = PySpin.CEnumEntryPtr(node_pixel_format.GetEntryByName('BayerRG8'))
                            if PySpin.IsAvailable(node_pixel_format_BayerRG8) and PySpin.IsReadable(node_pixel_format_BayerRG8):
                                # Retrieve the integer value from the entry node
                                pixel_format_BayerRG8 = node_pixel_format_BayerRG8.GetValue()
                                # Set integer as new value for enumeration node
                                node_pixel_format.SetIntValue(pixel_format_BayerRG8)
                            else:
                                print('Pixel format BayerRG8 not available...')
                        else:
                            print('Pixel format not available...')
                        # Apply minimum to offset X
                        node_offset_x = PySpin.CIntegerPtr(nodemap.GetNode('OffsetX'))
                        if PySpin.IsAvailable(node_offset_x) and PySpin.IsWritable(node_offset_x):
                            node_offset_x.SetValue(node_offset_x.GetMin())
                        else:
                            print('Offset X not available...')
                        # Apply minimum to offset Y
                        node_offset_y = PySpin.CIntegerPtr(nodemap.GetNode('OffsetY'))
                        if PySpin.IsAvailable(node_offset_y) and PySpin.IsWritable(node_offset_y):
                            node_offset_y.SetValue(node_offset_y.GetMin())
                        else:
                            print('Offset Y not available...')
                        # Set maximum width
                        node_width = PySpin.CIntegerPtr(nodemap.GetNode('Width'))
                        if PySpin.IsAvailable(node_width) and PySpin.IsWritable(node_width):
                            width_to_set = node_width.GetMax()
                            node_width.SetValue(width_to_set)
                        else:
                            print('Width not available...')
                        # Set maximum height
                        node_height = PySpin.CIntegerPtr(nodemap.GetNode('Height'))
                        if PySpin.IsAvailable(node_height) and PySpin.IsWritable(node_height):
                            height_to_set = node_height.GetMax()
                            node_height.SetValue(height_to_set)
                        else:
                            print('Height not available...')
                        cam.GainAuto.SetValue(PySpin.GainAuto_Off)
                        cam.BalanceWhiteAuto.SetValue(PySpin.BalanceWhiteAuto_Off)
                        cam.AdcBitDepth.SetValue(PySpin.AdcBitDepth_Bit8)
                        # print(cam.AcquisitionFrameRate.GetValue())
                        
                        self.camq_p2read.put('done')
                        method = self.camq.get()
                        if method == 'crop' or method == 'stim':
                            if method == 'crop':
                                isstim = False
                                
                            roi = self.frmDims
                            user_cfg = multiCam.read_config()
                            if method == 'stim' and isstim:
                                record_frame_rate = int(user_cfg['stimRate'])
                            else:
                                record_frame_rate = int(user_cfg[camStr]['framerate'])
                                
                            nodemap = cam.GetNodeMap()
                            
                            # Set width
                            node_width = PySpin.CIntegerPtr(nodemap.GetNode('Width'))
                            width_max = node_width.GetMax()
                            if method == 'stim' and isstim:
                                width_to_set = np.floor(width_max/roi[3]*user_cfg['stimXWYH'][1]/4)*4
                            else:
                                width_to_set = np.floor(width_max/roi[3]*user_cfg[camStr]['crop'][1]/4)*4
                            if PySpin.IsAvailable(node_width) and PySpin.IsWritable(node_width):
                                node_width.SetValue(int(width_to_set))
                            else:
                                print('Width not available...')
                            # Set height
                            node_height = PySpin.CIntegerPtr(nodemap.GetNode('Height'))
                            height_max = node_height.GetMax()
                            if method == 'stim' and isstim:
                                height_to_set = np.floor(height_max/roi[1]*user_cfg['stimXWYH'][3]/4)*4
                            else:
                                height_to_set = np.floor(height_max/roi[1]*user_cfg[camStr]['crop'][3]/4)*4
                            if PySpin.IsAvailable(node_height) and PySpin.IsWritable(node_height):
                                node_height.SetValue(int(height_to_set))
                            else:
                                print('Height not available...')
    
                            # Apply offset X
                            node_offset_x = PySpin.CIntegerPtr(nodemap.GetNode('OffsetX'))
                            if method == 'stim' and isstim:
                                offset_x = np.floor(width_max/roi[3]*user_cfg['stimXWYH'][0]/4)*4
                            else:
                                offset_x = np.floor(width_max/roi[3]*user_cfg[camStr]['crop'][0]/4)*4
                            if PySpin.IsAvailable(node_offset_x) and PySpin.IsWritable(node_offset_x):
                                node_offset_x.SetValue(int(offset_x))
                            else:
                                print('Offset X not available...')
                            # Apply offset Y
                            node_offset_y = PySpin.CIntegerPtr(nodemap.GetNode('OffsetY'))
                            if method == 'stim' and isstim:
                                offset_y = np.floor(height_max/roi[1]*user_cfg['stimXWYH'][2]/4)*4
                            else:
                                offset_y = np.floor(height_max/roi[1]*user_cfg[camStr]['crop'][2]/4)*4
                            if PySpin.IsAvailable(node_offset_y) and PySpin.IsWritable(node_offset_y):
                                node_offset_y.SetValue(int(offset_y))
                            else:
                                print('Offset Y not available...')
                                
                            if method == 'stim' and isstim:
                                aqW = user_cfg['stimXWYH'][1]
                                aqH = user_cfg['stimXWYH'][3]
                            else:
                                aqW = user_cfg[camStr]['crop'][1]
                                aqH = user_cfg[camStr]['crop'][3]
                            
                        else:
                            aqW = self.frmDims[3]
                            aqH = self.frmDims[1]
                            record_frame_rate = int(30)
                            isstim = False
                            
                            
                        exposure_time_request = int(user_cfg[camStr]['exposure'])
                        
                        cam.AcquisitionFrameRateEnable.SetValue(False)
                        if cam.ExposureAuto.GetAccessMode() != PySpin.RW:
                            print('Unable to disable automatic exposure. Aborting...')
                            continue
                        cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
                        if cam.ExposureTime.GetAccessMode() != PySpin.RW:
                            print('Unable to set exposure time. Aborting...')
                            continue
                        # Ensure desired exposure time does not exceed the maximum
                        exposure_time_to_set = floor(1/record_frame_rate*1000*1000)
                        if exposure_time_request <= exposure_time_to_set:
                            exposure_time_to_set = exposure_time_request
                        max_exposure = cam.ExposureTime.GetMax()
                        exposure_time_to_set = min(max_exposure, exposure_time_to_set)
                        cam.ExposureTime.SetValue(exposure_time_to_set)
                        cam.AcquisitionFrameRateEnable.SetValue(True)
                        
                        # Ensure desired frame rate does not exceed the maximum
                        max_frmrate = cam.AcquisitionFrameRate.GetMax()
                        exposure_time_to_set = min(max_frmrate, record_frame_rate)
                        
                        cam.AcquisitionFrameRate.SetValue(record_frame_rate)
                        exposure_time_to_set = cam.ExposureTime.GetValue()
                        record_frame_rate = cam.AcquisitionFrameRate.GetValue()
                        # max_exposure = cam.ExposureTime.GetMax()
                        # self.camq_p2read.put(exposure_time_to_set)
                        print('frame rate ' + user_cfg[camStr]['nickname'] + ' : ' + str(round(record_frame_rate)))
                        # self.camq_p2read.put(max_exposure)
                        self.camq_p2read.put(record_frame_rate)
                        self.camq_p2read.put(width_to_set)
                        self.camq_p2read.put(height_to_set)
                        
                        
                except:
                    exc_type, exc_obj, tb = sys.exc_info()
                    f = tb.tb_frame
                    lineno = tb.tb_lineno
                    filename = f.f_code.co_filename
                    linecache.checkcache(filename)
                    line = linecache.getline(filename, lineno, f.f_globals)
                    print('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))
                    print(self.camID + ' : ' + camStr)
                    if msg == 'updateSettings':
                        self.camq_p2read.put(30)
                        self.camq_p2read.put(30)
                        self.camq_p2read.put(30)
                    else:
                        self.camq_p2read.put('done')
            
            except Empty:
                pass
        
        

        
    