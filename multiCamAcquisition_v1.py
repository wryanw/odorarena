"""
multiCam toolbox
https://github.com/wryanw/multiCam
W Williamson, wallace.williamson@ucdenver.edu

"""


from __future__ import print_function
from multiprocessing import Array, Queue, Value
import wx
import wx.lib.dialogs
import os
import numpy as np
import time, datetime
import ctypes
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import matplotlib.patches as patches
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
import multiCam_PySpin_v1 as spin
import multiCam_utils as multiCam
import compressVideos_multiCam as compressVideos
import shutil
import pickle

# ###########################################################################
# Class for GUI MainFrame
# ###########################################################################
class ImagePanel(wx.Panel):

    def __init__(self, parent, gui_size, axesCt, **kwargs):
        wx.Panel.__init__(self, parent, -1,style=wx.SUNKEN_BORDER)
            
        self.figure = Figure()
        self.axes = list()
        if axesCt <= 3:
            if gui_size[0] > gui_size[1]:
                rowCt = 1
                colCt = axesCt
            else:
                colCt = 1
                rowCt = axesCt
            
        else:
            if gui_size[0] > gui_size[1]:
                rowCt = 2
                colCt = np.ceil(axesCt/2)
            else:
                colCt = 2
                rowCt = np.ceil(axesCt/2)
        a = 0
        for r in range(int(rowCt)):
            for c in range(int(colCt)):
                self.axes.append(self.figure.add_subplot(rowCt, colCt, a+1, frameon=True))
                self.axes[a].set_position([c*1/colCt+0.005,r*1/rowCt+0.005,1/colCt-0.01,1/rowCt-0.01])
                
        
                self.axes[a].xaxis.set_visible(False)
                self.axes[a].yaxis.set_visible(False)
                a+=1
            
        self.canvas = FigureCanvas(self, -1, self.figure)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
        self.SetSizer(self.sizer)
        self.Fit()

    def getfigure(self):
        """
        Returns the figure, axes and canvas
        """
        return(self.figure,self.axes,self.canvas)

class WidgetPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, -1,style=wx.SUNKEN_BORDER)

class MainFrame(wx.Frame):
    """Contains the main GUI and button boxes"""
    def __init__(self, parent):
        

# Settting the GUI size and panels design
        displays = (wx.Display(i) for i in range(wx.Display.GetCount())) # Gets the number of displays
        screenSizes = [display.GetGeometry().GetSize() for display in displays] # Gets the size of each display
        index = 0 # For display 1.
        screenW = screenSizes[index][0]
        screenH = screenSizes[index][1]
        
        self.user_cfg = multiCam.read_config()
        key_list = list()
        for cat in self.user_cfg.keys():
            key_list.append(cat)
        self.camStrList = list()
        for key in key_list:
            if 'cam' in key:
                self.camStrList.append(key)
        self.slist = list()
        for s in self.camStrList:
            if not self.user_cfg[s]['ismaster']:
                self.slist.append(str(self.user_cfg[s]['serial']))
            else:
                self.masterID = str(self.user_cfg[s]['serial'])
        
        self.camCt = len(self.camStrList)
        if self.camCt <= 3:
            scaleRefs = [0.6,0.9]
        else:
            scaleRefs = [0.7,0.8]   
        
        self.gui_size = (round(screenW*scaleRefs[0]),round(screenH*scaleRefs[1]))
        if screenW > screenH:
            self.gui_size = (round(screenW*scaleRefs[1]),round(screenH*scaleRefs[0]))
        wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = 'multiCam Acquisition - WRW',
                            size = wx.Size(self.gui_size), pos = wx.DefaultPosition, style = wx.RESIZE_BORDER|wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL )
        self.statusbar = self.CreateStatusBar()
        self.statusbar.SetStatusText("")

        self.SetSizeHints(wx.Size(self.gui_size)) #  This sets the minimum size of the GUI. It can scale now!
        
###################################################################################################################################################
# Spliting the frame into top and bottom panels. Bottom panels contains the widgets. The top panel is for showing images and plotting!
        self.guiDim = 0
        if screenH > screenW:
            self.guiDim = 1
        topSplitter = wx.SplitterWindow(self)
        self.image_panel = ImagePanel(topSplitter,self.gui_size, self.camCt)
        self.widget_panel = WidgetPanel(topSplitter)
        if self.guiDim == 0:
            topSplitter.SplitVertically(self.image_panel, self.widget_panel,sashPosition=self.gui_size[0]*0.75)#0.9
        else:
            topSplitter.SplitHorizontally(self.image_panel, self.widget_panel,sashPosition=self.gui_size[1]*0.75)#0.9
        topSplitter.SetSashGravity(0.5)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(topSplitter, 1, wx.EXPAND)
        self.SetSizer(sizer)

###################################################################################################################################################
# Add Buttons to the WidgetPanel and bind them to their respective functions.
        
        

        wSpace = 0
        wSpacer = wx.GridBagSizer(5, 5)
        
        camctrlbox = wx.StaticBox(self.widget_panel, label="Camera Control")
        bsizer = wx.StaticBoxSizer(camctrlbox, wx.HORIZONTAL)
        camsizer = wx.GridBagSizer(5, 5)
        
        bw = 76
        vpos = 0
        self.init = wx.ToggleButton(self.widget_panel, id=wx.ID_ANY, label="Initialize", size=(bw,-1))
        camsizer.Add(self.init, pos=(vpos,0), span=(1,3), flag=wx.ALL, border=wSpace)
        self.init.Bind(wx.EVT_TOGGLEBUTTON, self.initCams)
        
        self.reset = wx.Button(self.widget_panel, id=wx.ID_ANY, label="Reset", size=(bw, -1))
        camsizer.Add(self.reset, pos=(vpos,3), span=(1,3), flag=wx.ALL, border=wSpace)
        self.reset.Bind(wx.EVT_BUTTON, self.camReset)
        
        self.update_settings = wx.Button(self.widget_panel, id=wx.ID_ANY, label="Update Settings", size=(bw*2, -1))
        camsizer.Add(self.update_settings, pos=(vpos,6), span=(1,6), flag=wx.ALL, border=wSpace)
        self.update_settings.Bind(wx.EVT_BUTTON, self.updateSettings)
        self.update_settings.Enable(False)
        
        vpos+=1
        self.set_pellet_pos = wx.ToggleButton(self.widget_panel, id=wx.ID_ANY, label="Pellet", size=(bw, -1))
        camsizer.Add(self.set_pellet_pos, pos=(vpos,0), span=(0,3), flag=wx.TOP | wx.BOTTOM, border=3)
        self.set_pellet_pos.Bind(wx.EVT_TOGGLEBUTTON, self.setCrop)
        self.set_pellet_pos.Enable(False)
        
        
        self.set_roi = wx.ToggleButton(self.widget_panel, id=wx.ID_ANY, label="Hand ROI", size=(bw, -1))
        camsizer.Add(self.set_roi, pos=(vpos,3), span=(0,3), flag=wx.TOP, border=0)
        self.set_roi.Bind(wx.EVT_TOGGLEBUTTON, self.setCrop)
        self.set_roi.Enable(False)
        
        self.set_crop = wx.ToggleButton(self.widget_panel, id=wx.ID_ANY, label="Crop", size=(bw, -1))
        camsizer.Add(self.set_crop, pos=(vpos,6), span=(0,3), flag=wx.TOP, border=0)
        self.set_crop.Bind(wx.EVT_TOGGLEBUTTON, self.setCrop)
        self.set_crop.Enable(False)
        
        self.set_stim = wx.ToggleButton(self.widget_panel, id=wx.ID_ANY, label="Stim ROI", size=(bw, -1))
        camsizer.Add(self.set_stim, pos=(vpos,9), span=(0,3), flag=wx.TOP, border=0)
        self.set_stim.Bind(wx.EVT_TOGGLEBUTTON, self.setCrop)
        self.set_stim.Enable(False)

        vpos+=1
        self.play = wx.ToggleButton(self.widget_panel, id=wx.ID_ANY, label="Live", size=(bw, -1))
        camsizer.Add(self.play, pos=(vpos,0), span=(1,3), flag=wx.ALL, border=wSpace)
        self.play.Bind(wx.EVT_TOGGLEBUTTON, self.liveFeed)
        self.play.Enable(False)
        
        self.rec = wx.ToggleButton(self.widget_panel, id=wx.ID_ANY, label="Record", size=(bw, -1))
        camsizer.Add(self.rec, pos=(vpos,3), span=(1,3), flag=wx.ALL, border=wSpace)
        self.rec.Bind(wx.EVT_TOGGLEBUTTON, self.recordCam)
        self.rec.Enable(False)
        
        self.minRec = wx.TextCtrl(self.widget_panel, value='20', size=(50, -1))
        self.minRec.Enable(False)
        min_text = wx.StaticText(self.widget_panel, label='M:')
        camsizer.Add(self.minRec, pos=(vpos,7), span=(1,2), flag=wx.ALL, border=wSpace)
        camsizer.Add(min_text, pos=(vpos,6), span=(1,1), flag=wx.TOP, border=5)
        
        self.secRec = wx.TextCtrl(self.widget_panel, value='0', size=(50, -1))
        self.secRec.Enable(False)
        sec_text = wx.StaticText(self.widget_panel, label='S:')
        camsizer.Add(self.secRec, pos=(vpos,10), span=(1,2), flag=wx.ALL, border=wSpace)
        camsizer.Add(sec_text, pos=(vpos,9), span=(1,1), flag=wx.TOP, border=5)
        vpos+=4
        bsizer.Add(camsizer, 1, wx.EXPAND | wx.ALL, 5)
        wSpacer.Add(bsizer, pos=(0, 0), span=(vpos,3),flag=wx.EXPAND|wx.TOP|wx.LEFT|wx.RIGHT, border=5)
#       
        wSpace = 10
        
        self.slider = wx.Slider(self.widget_panel, -1, 0, 0, 100,size=(300, -1), style=wx.SL_HORIZONTAL | wx.SL_AUTOTICKS | wx.SL_LABELS )
        wSpacer.Add(self.slider, pos=(vpos,0), span=(0,3), flag=wx.LEFT, border=wSpace)
        self.slider.Enable(False)
        
        vpos+=1
        self.crop_rec = wx.CheckBox(self.widget_panel, id=wx.ID_ANY, label="Crop")
        wSpacer.Add(self.crop_rec, pos=(vpos,0), span=(0,1), flag=wx.LEFT, border=wSpace)
        self.crop_rec.SetValue(0)
        
        self.expt_id = wx.TextCtrl(self.widget_panel, id=wx.ID_ANY, value="SessionRef")
        wSpacer.Add(self.expt_id, pos=(vpos,1), span=(0,1), flag=wx.LEFT, border=wSpace)
        
        self.compress_vid = wx.Button(self.widget_panel, id=wx.ID_ANY, label="Compress Vids")
        wSpacer.Add(self.compress_vid, pos=(vpos,2), span=(0,1), flag=wx.LEFT, border=wSpace)
        self.compress_vid.Bind(wx.EVT_BUTTON, self.compressVid)

        vpos+=2
        start_text = wx.StaticText(self.widget_panel, label='Automate:')
        wSpacer.Add(start_text, pos=(vpos,0), span=(0,1), flag=wx.LEFT, border=wSpace)
        
        self.auto_pellet = wx.CheckBox(self.widget_panel, id=wx.ID_ANY, label="Pellet")
        wSpacer.Add(self.auto_pellet, pos=(vpos,1), span=(0,1), flag=wx.LEFT, border=wSpace)
        self.auto_pellet.SetValue(1)
        self.auto_stim = wx.CheckBox(self.widget_panel, id=wx.ID_ANY, label="Stimulus")
        wSpacer.Add(self.auto_stim, pos=(vpos,2), span=(0,1), flag=wx.LEFT, border=wSpace)
        self.auto_stim.SetValue(0)
        
        vpos+=2
        
        self.load_pellet = wx.Button(self.widget_panel, id=wx.ID_ANY, label="Load Pellet")
        wSpacer.Add(self.load_pellet, pos=(vpos,0), span=(0,1), flag=wx.LEFT, border=wSpace)
        self.load_pellet.Bind(wx.EVT_BUTTON, self.comFun)
        self.load_pellet.Enable(False)
        
        self.release_pellet = wx.Button(self.widget_panel, id=wx.ID_ANY, label="Release Pellet")
        wSpacer.Add(self.release_pellet, pos=(vpos,1), span=(0,1), flag=wx.LEFT, border=wSpace)
        self.release_pellet.Bind(wx.EVT_BUTTON, self.comFun)
        self.release_pellet.Enable(False)
        
        self.man_stim = wx.Button(self.widget_panel, id=wx.ID_ANY, label="Manual Stim")
        wSpacer.Add(self.man_stim, pos=(vpos,2), span=(0,1), flag=wx.LEFT, border=wSpace)
        self.man_stim.Bind(wx.EVT_BUTTON, self.comFun)
        self.man_stim.Enable(False)
        
        vpos+=3
        self.quit = wx.Button(self.widget_panel, id=wx.ID_ANY, label="Quit")
        wSpacer.Add(self.quit, pos=(vpos,0), span=(0,1), flag=wx.LEFT, border=wSpace)
        self.quit.Bind(wx.EVT_BUTTON, self.quitButton)
        self.Bind(wx.EVT_CLOSE, self.quitButton)

        self.widget_panel.SetSizer(wSpacer)
        wSpacer.Fit(self.widget_panel)
        self.widget_panel.Layout()
        
        
        self.liveTimer = wx.Timer(self, wx.ID_ANY)
        self.recTimer = wx.Timer(self, wx.ID_ANY)
        
        self.figure,self.axes,self.canvas = self.image_panel.getfigure()
        self.figure.canvas.draw()

        self.pellet_x = self.user_cfg['pelletXY'][0]
        self.pellet_y = self.user_cfg['pelletXY'][1]
        
        
        self.stimroi = np.asarray(self.user_cfg['stimXWYH'], int)
        self.roi = np.asarray(self.user_cfg['roiXWYH'], int)
        self.failCt = 0
        self.im = list()
        # self.frmDims = [0,135,0,180]
        self.frmDims = [0,270,0,360]
        self.camIDlsit = list()
        self.dlc = Value(ctypes.c_byte, 0)
        self.camaq = Value(ctypes.c_byte, 0)
        self.frmaq = Value(ctypes.c_int, 0)
        self.com = Value(ctypes.c_int, 0)
        self.dlc_frmct = 3
        self.pLoc = list()
        self.roirec = list()
        self.stimrec = list()
        self.croprec = list()
        self.croproi = list()
        self.frame = list()
        self.frameBuff = list()
        self.dtype = 'uint8'
        self.array = list()
        self.frmGrab = list()
        self.size = self.frmDims[1]*self.frmDims[3]
        self.shape = [self.frmDims[1], self.frmDims[3]]
        frame = np.zeros(self.shape, dtype='ubyte')
        frameBuff = np.zeros(self.size, dtype='ubyte')
        for ndx, s in enumerate(self.camStrList):
            self.camIDlsit.append(str(self.user_cfg[s]['serial']))
            self.croproi.append(self.user_cfg[s]['crop'])
            self.array.append(Array(ctypes.c_ubyte, self.size))
            self.frmGrab.append(Value(ctypes.c_byte, 0))
            self.frame.append(frame)
            self.frameBuff.append(frameBuff)
            self.im.append(self.axes[ndx].imshow(self.frame[ndx],cmap='gray'))
            self.im[ndx].set_clim(0,255)
            self.points = [-10,-10,1.0]
            circle = [patches.Circle((-10, -10), radius=5, fc=[0.8,0,0], alpha=0.0)]
            self.pLoc.append(self.axes[ndx].add_patch(circle[0]))
            cpt = self.roi
            rec = [patches.Rectangle((cpt[0],cpt[2]), cpt[1], cpt[3], fill=False, ec = [0.25,0.75,0.25], linewidth=2, linestyle='-',alpha=0.0)]
            self.roirec.append(self.axes[ndx].add_patch(rec[0]))
            
            cpt = self.croproi[ndx]
            rec = [patches.Rectangle((cpt[0],cpt[2]), cpt[1], cpt[3], fill=False, ec = [0.25,0.25,0.75], linewidth=2, linestyle='-',alpha=0.0)]
            self.croprec.append(self.axes[ndx].add_patch(rec[0]))
            
            cpt = self.stimroi
            rec = [patches.Rectangle((cpt[0],cpt[2]), cpt[1], cpt[3], fill=False, ec = [0.5,0.5,0.5], linewidth=2, linestyle='-',alpha=0.0)]
            self.stimrec.append(self.axes[ndx].add_patch(rec[0]))
            
            if self.user_cfg['axesRef'] == s:
                self.pelletAxes = self.axes[ndx]
                self.pLoc[ndx].set_center([self.pellet_x,self.pellet_y])
            if self.user_cfg['stimAxes'] == s:
                self.stimAxes = self.axes[ndx]
                
                
                
        self.figure.canvas.draw()
        self.canvas.mpl_connect('button_press_event', self.onClick)
        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyPressed)


    
    def OnKeyPressed(self, event):
        # print(event.GetModifiers())
        # print(event.GetKeyCode())
        if event.GetKeyCode() == wx.WXK_RETURN or event.GetKeyCode() == wx.WXK_NUMPAD_ENTER:
            if self.set_pellet_pos.GetValue():
                self.user_cfg['pelletXY'][0] = self.pellet_x
                self.user_cfg['pelletXY'][1] = self.pellet_y
            elif self.set_roi.GetValue():
                self.user_cfg['roiXWYH'] = np.ndarray.tolist(self.roi)
            elif self.set_crop.GetValue():
                ndx = self.axes.index(self.cropAxes)
                s = self.camStrList[ndx]
                self.user_cfg[s]['crop'] = np.ndarray.tolist(self.croproi[ndx])
        
            multiCam.write_config(self.user_cfg)
            self.set_pellet_pos.SetValue(False)
            self.set_roi.SetValue(False)
            self.set_crop.SetValue(False)
            self.widget_panel.Enable(True)
            self.play.SetFocus()
        elif event.GetKeyCode() == 314: #LEFT
            x = -1
            y = 0
        elif event.GetKeyCode() == 316: #RIGHT
            x = 1
            y = 0
        elif event.GetKeyCode() == 315: #UP
            x = 0
            y = -1
        elif event.GetKeyCode() == 317: #DOWN
            x = 0
            y = 1
        elif event.GetKeyCode() == 127: #DELETE
            if self.set_crop.GetValue():
                ndx = self.axes.index(self.cropAxes)
                self.croproi[ndx][0] = 0
                self.croproi[ndx][2] = 0
                self.croprec[ndx].set_alpha(0)
                multiCam.write_config(self.user_cfg)
                self.set_crop.SetValue(False)
                self.widget_panel.Enable(True)
                self.play.SetFocus()
                self.figure.canvas.draw()
        else:
            event.Skip()
            
        if self.set_pellet_pos.GetValue():
            self.pellet_x+=x
            self.pellet_y+=y
            self.drawROI()
        elif self.set_roi.GetValue():
            self.roi[0]+=x
            self.roi[2]+=y
            self.drawROI()
        elif self.set_crop.GetValue():
            ndx = self.axes.index(self.cropAxes)
            self.croproi[ndx][0]+=x
            self.croproi[ndx][2]+=y
            self.drawROI()
        elif self.set_stim.GetValue():
            self.stimroi[0]+=x
            self.stimroi[2]+=y
            self.drawROI()
            
            
    def drawROI(self):
        ndx = self.axes.index(self.pelletAxes)
        if self.set_pellet_pos.GetValue():
            self.pLoc[ndx].set_center([self.pellet_x,self.pellet_y])
            self.pLoc[ndx].set_alpha(0.6)
        elif self.set_roi.GetValue():
            self.roirec[ndx].set_x(self.roi[0])
            self.roirec[ndx].set_y(self.roi[2])
            self.roirec[ndx].set_width(self.roi[1])
            self.roirec[ndx].set_height(self.roi[3])
            self.roirec[ndx].set_alpha(0.6)
        elif self.set_crop.GetValue():
            ndx = self.axes.index(self.cropAxes)
            self.croprec[ndx].set_x(self.croproi[ndx][0])
            self.croprec[ndx].set_y(self.croproi[ndx][2])
            self.croprec[ndx].set_width(self.croproi[ndx][1])
            self.croprec[ndx].set_height(self.croproi[ndx][3])
            if not self.croproi[ndx][0] == 0:
                self.croprec[ndx].set_alpha(0.6)
        elif self.set_stim.GetValue():
            self.stimrec[ndx].set_x(self.stimroi[0])
            self.stimrec[ndx].set_y(self.stimroi[2])
            self.stimrec[ndx].set_width(self.stimroi[1])
            self.stimrec[ndx].set_height(self.stimroi[3])
            self.stimrec[ndx].set_alpha(0.6)
        self.figure.canvas.draw()
        
        
    def onClick(self,event):
        self.user_cfg = multiCam.read_config()
        if self.set_pellet_pos.GetValue():
            ndx = self.axes.index(event.inaxes)
            self.pelletAxes = event.inaxes
            self.user_cfg['axesRef'] = self.camStrList[ndx]
            self.pellet_x = int(event.xdata)
            self.pellet_y = int(event.ydata)
        elif self.set_roi.GetValue():
            ndx = self.axes.index(event.inaxes)
            self.pelletAxes = event.inaxes
            self.user_cfg['axesRef'] = self.camStrList[ndx]
            self.roi = np.asarray(self.user_cfg['roiXWYH'], int)
            roi_x = event.xdata
            roi_y = event.ydata
            self.roi = np.asarray([roi_x-self.roi[1]/2,self.roi[1],roi_y-self.roi[3]/2,self.roi[3]], int)
        elif self.set_crop.GetValue():
            self.cropAxes = event.inaxes
            ndx = self.axes.index(event.inaxes)
            s = self.camStrList[ndx]
            self.croproi[ndx] = self.user_cfg[s]['crop']
            roi_x = event.xdata
            roi_y = event.ydata
            self.croproi[ndx] = np.asarray([roi_x-self.croproi[ndx][1]/2,self.croproi[ndx][1],
                                            roi_y-self.croproi[ndx][3]/2,self.croproi[ndx][3]], int)
        elif self.set_stim.GetValue():
            ndx = self.axes.index(event.inaxes)
            self.stimAxes = event.inaxes
            self.user_cfg['stimAxes'] = self.camStrList[ndx]
            self.stimroi = np.asarray(self.user_cfg['stimXWYH'], int)
            roi_x = event.xdata
            roi_y = event.ydata
            self.stimroi = np.asarray([roi_x-self.stimroi[1]/2,self.stimroi[1],
                                       roi_y-self.stimroi[3]/2,self.stimroi[3]], int)
            
            
        self.drawROI()
                
    def comFun(self, event):
        if self.com.value < 0:
            return
        waitval = 0
        while not self.com.value == 0:
            time.sleep(1)
            waitval+=1
            if waitval > 10:
                break
            
        if self.load_pellet == event.GetEventObject():
            self.com.value = 1
        elif self.release_pellet == event.GetEventObject():
            self.com.value = 2
        elif self.man_stim == event.GetEventObject():
            self.com.value = 3
        
    def setCrop(self, event):
        self.widget_panel.Enable(False)
        
    def compressVid(self, event):
        compressThread = compressVideos.multiCam_compress()
        compressThread.start()
        
    def camReset(self,event):
        self.initThreads()
        self.camaq.value = 2
        self.startAq()
        time.sleep(3)
        self.stopAq()
        self.deinitThreads()
        print('\n*** CAMERAS RESET ***\n')
             
    def liveFeed(self, event):
        if self.play.GetLabel() == 'Abort':
            self.rec.SetValue(False)
            self.recordCam(event)
            
            if wx.MessageBox("Are you sure?", caption="Abort", style=wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION):
                shutil.rmtree(self.sess_dir)
            self.play.SetValue(False)
                        
        elif self.play.GetValue() == True:
            if not self.liveTimer.IsRunning():
                if self.auto_pellet.GetValue():
                    if not self.pellet_x == 0:
                        if not self.roi[0] == 0:
                            self.pellet_timing = time.time()
                            self.pellet_status = 2
                self.camaq.value = 1
                self.startAq()
                self.liveTimer.Start(150)
                self.play.SetLabel('Stop')
            
            self.rec.Enable(False)
            self.minRec.Enable(False)
            self.secRec.Enable(False)
            self.update_settings.Enable(False)
            self.expt_id.Enable(False)
            self.set_roi.Enable(False)
            self.set_crop.Enable(False)
            self.set_pellet_pos.Enable(False)
            
        else:
            if self.liveTimer.IsRunning():
                self.liveTimer.Stop()
            self.stopAq()
            time.sleep(2)
            self.play.SetLabel('Live')
            
            self.rec.Enable(True)
            self.minRec.Enable(True)
            self.secRec.Enable(True)
            self.update_settings.Enable(True)
            self.expt_id.Enable(True)
            self.set_roi.Enable(True)
            self.set_crop.Enable(True)
            self.set_pellet_pos.Enable(True)
            
            
    def pelletHandler(self, pim, roi):
        # events    0 - release pellet
        #           1 - load pellet
        #           2 - waiting to lose it
        if self.com.value < 0:
            return
        objDetected = False
        if pim > 50:
            objDetected = True
        
        if self.pellet_status == 0:
            if (time.time()-self.pellet_timing) > 7:
                if roi < 50:
                    self.pellet_status = 1
                    self.pellet_timing = time.time()
                    self.com.value = 2
                
        elif self.pellet_status == 1:
            if objDetected:
                self.pellet_status = 2
                self.pellet_timing = time.time()
                self.failCt = 0
            elif (time.time()-self.pellet_timing) > 3:
                self.failCt+=1
                if self.failCt > 7:
                    self.failCt = 0
                    beepList = [1,1,1]
                    self.auto_pellet.SetValue(0)
                    self.pellet_timing = time.time()
                    self.pellet_status = 2
                    for d in beepList: 
                        duration = d  # seconds
                        freq = 440  # Hz
                        os.system('play -nq -t alsa synth {} sine {}'.format(duration, freq))
                        time.sleep(d)
                elif round(self.failCt/2) == self.failCt/2 and self.failCt > 3:
                    self.com.value = 4
                    self.pellet_status = 2
                    self.pellet_timing = time.time()
                else:
                    self.pellet_status = 0
                    self.pellet_timing = time.time()
                    self.com.value = 1
        elif self.pellet_status == 2:
            if not objDetected:
                if (time.time()-self.pellet_timing) > 3:
                    self.pellet_status = 0
                    self.pellet_timing = time.time()
                    self.com.value = 1
            else:
                self.pellet_timing = time.time()
             
                
    def vidPlayer(self, event):
        if self.camaq.value == 2:
            return
        for ndx, im in enumerate(self.im):
            if self.frmGrab[ndx].value == 1:
                self.frameBuff[ndx][0:] = np.frombuffer(self.array[ndx].get_obj(), self.dtype, self.size)
                frame = self.frameBuff[ndx][0:self.dispSize[ndx]].reshape([self.h[ndx], self.w[ndx]])
                self.frame[ndx][self.y1[ndx]:self.y2[ndx],self.x1[ndx]:self.x2[ndx]] = frame
                im.set_data(self.frame[ndx])
                if self.auto_pellet.GetValue():
                    if not self.pellet_x == 0:
                        if not self.roi[0] == 0:
                            if self.pelletAxes == self.axes[ndx]:
                                span = 10
                                cpt = np.asarray([self.pellet_x-span,span*2+1,self.pellet_y-span,span*2+1], int)
                                pim = self.frame[ndx][cpt[2]:cpt[2]+cpt[3],cpt[0]:cpt[0]+cpt[1]]
                                cpt = self.roi
                                roi = self.frame[ndx][cpt[2]:cpt[2]+cpt[3],cpt[0]:cpt[0]+cpt[1]]
                                self.pelletHandler(np.mean(pim[:]),np.mean(roi[:]))
                self.frmGrab[ndx].value = 0
                
            
        self.figure.canvas.draw()
        
    def autoCapture(self, event):
        self.sliderTabs+=self.sliderRate
        if self.sliderTabs > self.slider.GetMax():
            self.rec.SetValue(False)
            self.recordCam(event)
            self.slider.SetValue(0)
        else:
            self.slider.SetValue(round(self.sliderTabs))
            self.vidPlayer(event)
        
    def recordCam(self, event):
        if self.rec.GetValue():
            
            liveRate = 1000
            self.Bind(wx.EVT_TIMER, self.autoCapture, self.recTimer)
            if int(self.minRec.GetValue()) == 0 and int(self.secRec.GetValue()) == 0:
                return
            totTime = int(self.secRec.GetValue())+int(self.minRec.GetValue())*60
            spaceneeded = 0
            for ndx, w in enumerate(self.aqW):
                recSize = w*self.aqH[ndx]*3*self.recSet[ndx]*totTime
                spaceneeded+=recSize
                
            self.slider.SetMax(100)
            self.slider.SetMin(0)
            self.slider.SetValue(0)
            self.sliderTabs = 0
            self.sliderRate = 100/(totTime/(liveRate/1000))
            
            date_string = datetime.datetime.now().strftime("%Y%m%d")
            base_dir = os.path.join(self.user_cfg['raw_data_dir'], date_string, self.user_cfg['unitRef'])
            if not os.path.exists(base_dir):
                os.makedirs(base_dir)
            freespace = shutil.disk_usage(base_dir)[2]
            if spaceneeded > freespace:
                dlg = wx.MessageDialog(parent=None,message="There is not enough disk space for the requested duration.",
                                       caption="Warning!", style=wx.OK|wx.ICON_EXCLAMATION)
                dlg.ShowModal()
                dlg.Destroy()
                self.rec.SetValue(False)
                return
            prev_expt_list = [name for name in os.listdir(base_dir) if name.startswith('session')]
            file_count = len(prev_expt_list)+1
            sess_string = '%s%03d' % ('session', file_count)
            self.sess_dir = os.path.join(base_dir, sess_string)
            if not os.path.exists(self.sess_dir):
                os.makedirs(self.sess_dir)
            multiCam.read_metadata
            self.meta,ruamelFile = multiCam.metadata_template()
            for ndx, s in enumerate(self.camStrList):
                
                camset = {'serial':self.user_cfg[s]['serial'],
                      'ismaster':self.user_cfg[s]['ismaster'],
                      'crop':self.user_cfg[s]['crop'],
                      'exposure': self.user_cfg[s]['exposure'],
                      'framerate': self.user_cfg[s]['framerate'],
                      'bin': self.user_cfg[s]['bin'],
                      'nickname': self.user_cfg[s]['nickname']}
                self.meta[s]=camset
            
            self.meta['unitRef']=self.user_cfg['unitRef']
            self.meta['duration (s)']=totTime
            self.meta['ID']=self.expt_id.GetValue()
            self.meta['placeholderA']='info'
            self.meta['placeholderB']='info'
            self.meta['Designer']='name'
            self.meta['Stim']='none'
            self.meta['axesRef']='cam0'
            self.meta['pelletXY']=self.user_cfg['pelletXY']
            self.meta['roiXWYH']=self.user_cfg['roiXWYH']
            self.meta['stimAxes']=self.user_cfg['stimAxes']
            self.meta['stimXWYH']=self.user_cfg['stimXWYH']
            self.meta['StartTime']=datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            self.meta['Collection']='info'
            meta_name = '%s_%s_%s_metadata.yaml' % (date_string, self.user_cfg['unitRef'], sess_string)
            self.metapath = os.path.join(self.sess_dir,meta_name)
            for ndx, s in enumerate(self.camStrList):
                camID = str(self.user_cfg[s]['serial'])
                self.camq[camID].put('recordPrep')
                name_base = '%s_%s_%s_%s' % (date_string, self.user_cfg['unitRef'], sess_string, self.user_cfg[s]['nickname'])
                path_base = os.path.join(self.sess_dir,name_base)
                self.camq[camID].put(path_base)
                self.camq_p2read[camID].get()
                
            self.minRec.Enable(False)
            self.secRec.Enable(False)
            self.update_settings.Enable(False)
            self.expt_id.Enable(False)
            self.set_roi.Enable(False)
            self.set_crop.Enable(False)
            self.set_pellet_pos.Enable(False)
            
            
            if not self.recTimer.IsRunning():
                if self.auto_pellet.GetValue():
                    if not self.pellet_x == 0:
                        if not self.roi[0] == 0:
                            self.pellet_timing = time.time()
                            self.pellet_status = 2
                
                self.camaq.value = 1
                self.startAq()
                self.recTimer.Start(liveRate)
            self.rec.SetLabel('Stop')
            self.play.SetLabel('Abort')
        else:
            self.meta['duration (s)']=round(self.meta['duration (s)']*(self.sliderTabs/100))
            multiCam.write_metadata(self.meta, self.metapath)
            if self.recTimer.IsRunning():
                self.recTimer.Stop()
            self.stopAq()
            time.sleep(2)
            self.rec.SetLabel('Record')
            self.play.SetLabel('Play')
            mv = multiCam.moveVids()
            mv.start()
            # compressThread = compressVideos.multiCam_compress()
            # compressThread.start()
            self.slider.SetValue(0)
            self.minRec.Enable(True)
            self.secRec.Enable(True)
            self.update_settings.Enable(True)
            self.expt_id.Enable(True)
            self.set_roi.Enable(True)
            self.set_crop.Enable(True)
            self.set_pellet_pos.Enable(True)
            
            
    
    def initThreads(self):
        self.camq = dict()
        self.camq_p2read = dict()
        self.cam = list()
        for ndx, camID in enumerate(self.camIDlsit):
            self.camq[camID] = Queue()
            self.camq_p2read[camID] = Queue()
            self.cam.append(spin.Run_Cams(self.camq[camID], self.camq_p2read[camID],
                                               self.array[ndx], self.frmGrab[ndx], camID, self.camIDlsit,
                                               self.frmDims, self.dlc_frmct, self.camaq,
                                               self.frmaq, self.com))
            self.cam[ndx].start()
        
        self.camq[self.masterID].put('InitM')
        self.camq_p2read[self.masterID].get()
        for s in self.slist:
            self.camq[s].put('InitS')
            self.camq_p2read[s].get()
            
    def deinitThreads(self):
        for n, camID in enumerate(self.camIDlsit):
            self.camq[camID].put('Release')
            self.camq_p2read[camID].get()
            self.camq[camID].close()
            self.camq_p2read[camID].close()
            self.cam[n].terminate()
            
    def startAq(self):
        self.camq[self.masterID].put('Start')
        for s in self.slist:
            self.camq[s].put('Start')
        self.camq[self.masterID].put('TrigOff')
        
    def stopAq(self):
        self.camaq.value = 0
        for s in self.slist:
            self.camq[s].put('Stop')
            self.camq_p2read[s].get()
        self.camq[self.masterID].put('Stop')
        self.camq_p2read[self.masterID].get()
        
    def updateSettings(self, event):
        self.user_cfg = multiCam.read_config()
        self.aqW = list()
        self.aqH = list()
        self.recSet = list()
        for n, camID in enumerate(self.camIDlsit):
            try:
                self.camq[camID].put('updateSettings')
                self.camq_p2read[camID].get()
                if self.crop_rec.GetValue():
                    if self.auto_stim.GetValue():
                        self.camq[camID].put('stim')
                    else:
                        self.camq[camID].put('crop')
                else:
                    self.camq[camID].put('full')
            
                self.recSet.append(self.camq_p2read[camID].get())
                self.aqW.append(self.camq_p2read[camID].get())
                self.aqH.append(self.camq_p2read[camID].get())
            except:
                print('\nTrying to fix.  Please wait...\n')
                self.deinitThreads()
                self.camReset(event)
                self.initThreads()
                self.camq[camID].put('updateSettings')
                self.camq_p2read[camID].get()
                if self.crop_rec.GetValue():
                    if self.auto_stim.GetValue():
                        self.camq[camID].put('stim')
                    else:
                        self.camq[camID].put('crop')
                else:
                    self.camq[camID].put('full')
            
                self.recSet.append(self.camq_p2read[camID].get())
                self.aqW.append(self.camq_p2read[camID].get())
                self.aqH.append(self.camq_p2read[camID].get())
            
    def initCams(self, event):
        if self.init.GetValue() == True:
            self.Enable(False)
            
            self.colormap = plt.get_cmap('jet')
            self.colormap = self.colormap.reversed()
            self.markerSize = 6
            self.alpha = 0.7
            
            self.initThreads()
            self.updateSettings(event)
            
            self.Bind(wx.EVT_TIMER, self.vidPlayer, self.liveTimer)
            
            self.camaq.value = 1
            self.startAq()
            time.sleep(1)
            self.camaq.value = 0
            self.stopAq()
            self.x1 = list()
            self.x2 = list()
            self.y1 = list()
            self.y2 = list()
            self.h = list()
            self.w = list()
            self.dispSize = list()
            for ndx, im in enumerate(self.im):
                self.frame[ndx] = np.zeros(self.shape, dtype='ubyte')
                self.frameBuff[ndx][0:] = np.frombuffer(self.array[ndx].get_obj(), self.dtype, self.size)
                if self.crop_rec.GetValue():
                    self.h.append(self.croproi[ndx][3])
                    self.w.append(self.croproi[ndx][1])
                    self.y1.append(self.croproi[ndx][2])
                    self.x1.append(self.croproi[ndx][0])
                    self.dispSize.append(self.h[ndx]*self.w[ndx])
                else:
                    self.h.append(self.frmDims[1])
                    self.w.append(self.frmDims[3])
                    self.y1.append(self.frmDims[0])
                    self.x1.append(self.frmDims[2])
                    self.dispSize.append(self.h[ndx]*self.w[ndx])
                self.y2.append(self.y1[ndx]+self.h[ndx])
                self.x2.append(self.x1[ndx]+self.w[ndx])
                
                frame = self.frameBuff[ndx][0:self.dispSize[ndx]].reshape([self.h[ndx], self.w[ndx]])
                self.frame[ndx][self.y1[ndx]:self.y2[ndx],self.x1[ndx]:self.x2[ndx]] = frame
                im.set_data(self.frame[ndx])
                
                    
                if not self.croproi[ndx][0] == 0:
                    self.croprec[ndx].set_alpha(0.6)

                if not self.pellet_x == 0:
                    if not self.roi[0] == 0:
                        if self.pelletAxes == self.axes[ndx]:
                            self.pLoc[ndx].set_alpha(0.6)
                            self.roirec[ndx].set_alpha(0.6)
                            
                if not self.stimroi[0] == 0:
                    if self.stimAxes == self.axes[ndx]:
                        self.stimrec[ndx].set_alpha(0.6)
            self.figure.canvas.draw()
            
            self.init.SetLabel('Release')
            self.play.Enable(True)
            self.rec.Enable(True)
            self.minRec.Enable(True)
            self.secRec.Enable(True)
            self.reset.Enable(False)
            self.update_settings.Enable(True)
            self.auto_stim.Enable(False)
            self.set_roi.Enable(True)
            self.set_crop.Enable(True)
            self.set_pellet_pos.Enable(True)
            self.crop_rec.Enable(False)
            
            if not self.com.value < 0:
                self.man_stim.Enable(True)
                self.load_pellet.Enable(True)
                self.release_pellet.Enable(True)
                    
            self.Enable(True)
        else:
            self.man_stim.Enable(False)
            self.load_pellet.Enable(False)
            self.release_pellet.Enable(False)
                    
            for ndx, im in enumerate(self.im):
                self.frame[ndx] = np.zeros(self.shape, dtype='ubyte')
                im.set_data(self.frame[ndx])
                self.croprec[ndx].set_alpha(0)
                self.pLoc[ndx].set_alpha(0)
                self.roirec[ndx].set_alpha(0)
                self.stimrec[ndx].set_alpha(0)
            self.figure.canvas.draw()
            
            self.init.SetLabel('Enable')
            self.play.Enable(False)
            self.rec.Enable(False)
            self.minRec.Enable(False)
            self.secRec.Enable(False)
            self.reset.Enable(True)
            self.update_settings.Enable(False)
            self.auto_stim.Enable(True)
            self.set_roi.Enable(False)
            self.set_crop.Enable(False)
            self.set_pellet_pos.Enable(False)
            self.crop_rec.Enable(True)
            self.deinitThreads()
            
    def quitButton(self, event):
        """
        Quits the GUI
        """
        print('Close event called')
        if self.play.GetValue():
            self.play.SetValue(False)
            self.liveFeed(event)
        if self.rec.GetValue():
            self.rec.SetValue(False)
            self.recordCam(event)
        if self.init.GetValue():
            self.init.SetValue(False)
            self.initCams(event)
        self.statusbar.SetStatusText("")
        self.Destroy()
    
def show():
    app = wx.App()
    MainFrame(None).Show()
    app.MainLoop()

if __name__ == '__main__':
    user_cfg = multiCam.read_config()
    if user_cfg['cam1'] == None:
        print('Camera serial numbers are missing')
    else:
        show()