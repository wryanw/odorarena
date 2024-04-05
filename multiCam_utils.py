"""
DeepLabCut2.0 Toolbox
https://github.com/AlexEMG/DeepLabCut
A Mathis, alexander.mathis@bethgelab.org
T Nath, nath@rowland.harvard.edu
M Mathis, mackenzie@post.harvard.edu

Boilerplate project creation inspired from DeepLabChop
by Ronny Eichler
"""
import os, socket
from pathlib import Path
import numpy as np
import os.path
import yaml
import ruamel.yaml
import glob
import os
from pathlib import PurePath
import cv2
import sys, linecache
import shutil
import pickle
from multiprocessing import Process

class moveVids(Process):
    def __init__(self):
        super().__init__()
        
    def run(self):
        try:
            dirlist = list()
            destlist = list()
            user_cfg = read_config()
            read_dir = user_cfg['raw_data_dir']
            write_dir = user_cfg['compressed_video_dir']
            prev_date_list = [name for name in os.listdir(read_dir)]
            for f in prev_date_list:
                unit_dirR = os.path.join(read_dir, f, user_cfg['unitRef'])
                unit_dirW = os.path.join(write_dir, f, user_cfg['unitRef'])
                if os.path.exists(unit_dirR):
                    prev_expt_list = [name for name in os.listdir(unit_dirR)]
                    for s in prev_expt_list:
                        dirlist.append(os.path.join(unit_dirR, s))
                        destlist.append(os.path.join(unit_dirW, s))
                            
            
            for ndx, s in enumerate(dirlist):
                avi_list = os.path.join(s, '*.avi')
                vid_list = glob.glob(avi_list)
                if not os.path.exists(destlist[ndx]):
                    os.makedirs(destlist[ndx])
                if len(vid_list):
                    for v in vid_list:
                        vid_name = PurePath(v)
                        dest_path = os.path.join(destlist[ndx], vid_name.stem+'.avi')
                        passtest = self.testVids(v,str(dest_path))
                        if not passtest:
                            shutil.copyfile(v,dest_path)
                            
                    passvals = list()
                    for v in vid_list:
                        vid_name = PurePath(v)
                        dest_path = os.path.join(destlist[ndx], vid_name.stem+'.avi')
                        passval = self.testVids(v,str(dest_path))
                        passvals.append(passval)
                        if passval:
                            os.remove(v)
                            print('Deleted original video')
                        else:
                            print('Error while moving')
                metafiles = glob.glob(os.path.join(s,'*'))
                for m in metafiles:
                    mname = PurePath(m).name
                    mdest = os.path.join(destlist[ndx],mname)
                    if not os.path.isfile(mdest):
                        shutil.copyfile(m,mdest)
        except:
            exc_type, exc_obj, tb = sys.exc_info()
            f = tb.tb_frame
            lineno = tb.tb_lineno
            filename = f.f_code.co_filename
            linecache.checkcache(filename)
            line = linecache.getline(filename, lineno, f.f_globals)
            print('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))
                
    def testVids(self, v, dest_path):
        try:
            vid = cv2.VideoCapture(v)
            numberFramesA = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))
            vid = cv2.VideoCapture(str(dest_path))
            numberFramesB = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))
            if numberFramesA == numberFramesB:
                passval = True
            else:
                passval = False
        except:
            passval = False
            exc_type, exc_obj, tb = sys.exc_info()
            f = tb.tb_frame
            lineno = tb.tb_lineno
            filename = f.f_code.co_filename
            linecache.checkcache(filename)
            line = linecache.getline(filename, lineno, f.f_globals)
            print('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))
            
        return passval

                
def MakeTest_pose_yaml(dictionary, keys2save, saveasfile):
    dict_test = {}
    for key in keys2save:
        dict_test[key] = dictionary[key]

    dict_test['scoremap_dir'] = 'test'
    with open(saveasfile, "w") as f:
        yaml.dump(dict_test, f)

def MakeTrain_pose_yaml(itemstochange,saveasconfigfile,defaultconfigfile):
    raw = open(defaultconfigfile).read()
    docs = []
    for raw_doc in raw.split('\n---'):
        try:
            docs.append(yaml.load(raw_doc,Loader=yaml.SafeLoader))
        except SyntaxError:
            docs.append(raw_doc)

    for key in itemstochange.keys():
        docs[0][key] = itemstochange[key]

    with open(saveasconfigfile, "w") as f:
        yaml.dump(docs[0], f)
    return docs[0]

def boxitintoacell(joints):
    ''' Auxiliary function for creating matfile.'''
    outer = np.array([[None]], dtype=object)
    outer[0, 0] = np.array(joints, dtype='int64')
    return outer

def SplitTrials(trialindex, trainFraction=0.8):
    ''' Split a trial index into train and test sets. Also checks that the trainFraction is a two digit number between 0 an 1. The reason
    is that the folders contain the trainfraction as int(100*trainFraction). '''
    if trainFraction>1 or trainFraction<0:
        print("The training fraction should be a two digit number between 0 and 1; i.e. 0.95. Please change accordingly.")
        return ([],[])

    if abs(trainFraction-round(trainFraction,2))>0:
        print("The training fraction should be a two digit number between 0 and 1; i.e. 0.95. Please change accordingly.")
        return ([],[])
    else:
        trainsetsize = int(len(trialindex) * round(trainFraction,2))
        shuffle = np.random.permutation(trialindex)
        testIndexes = shuffle[trainsetsize:]
        trainIndexes = shuffle[:trainsetsize]
        
        return (trainIndexes, testIndexes)
    
def cam_config_template():
    """
    Creates a template for config.yaml file. This specific order is preserved while saving as yaml file.
    """
    yaml_str = """\
# Camera reference (enter serial numbers for each)
    cam1:
    cam2:
    cam3:
    cam4:
    \n
    
# User information
    unitRef:
    raw_data_dir:
    compressed_video_dir:
    COM:
    \n

# Stim ROI
    stimAxes:
    stimXWYH:
    stimRate:
    \n

# Pellet and ROI
    axesRef:
    pelletXY:
    roiXWYH:
    \n
    """
    ruamelFile = ruamel.yaml.YAML()
    cfg_file = ruamelFile.load(yaml_str)
    return cfg_file, ruamelFile

def read_config():
    """
    Reads structured config file

    """
    usrdatadir = os.path.dirname(os.path.realpath(__file__))
    configname = os.path.join(usrdatadir, 'userdata.yaml')
    ruamelFile = ruamel.yaml.YAML()
    path = Path(configname)
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                cfg = ruamelFile.load(f)
        except Exception as err:
            if err.args[2] == "could not determine a constructor for the tag '!!python/tuple'":
                with open(path, 'r') as ymlfile:
                  cfg = yaml.load(ymlfile,Loader=yaml.SafeLoader)
                  write_config(cfg)
    else:
        cfg,ruamelFile = cam_config_template()
        camset = {'serial':12345678,
                  'ismaster':False,
                  'crop': [0, 360, 0, 270],
                  'exposure': 5000,
                  'framerate': 150,
                  'bin': 1,
                  'nickname': 'OneWordLettersOnly'}
        cfg['cam1']=camset
        camset = {'serial':12345678,
                  'ismaster':False,
                  'crop': [0, 360, 0, 270],
                  'exposure': 5000,
                  'framerate': 150,
                  'bin': 1,
                  'nickname': 'OneWordLettersOnly'}
        cfg['cam2']=camset
        camset = {'serial':12345678,
                  'ismaster':False,
                  'crop': [0, 360, 0, 270],
                  'exposure': 5000,
                  'framerate': 150,
                  'bin': 1,
                  'nickname': 'OneWordLettersOnly'}
        cfg['cam3']=camset
        camset = {'serial':12345678,
                  'ismaster':False,
                  'crop': [0, 360, 0, 270],
                  'exposure': 5000,
                  'framerate': 150,
                  'bin': 1,
                  'nickname': 'OneWordLettersOnly'}
        cfg['cam4']=camset
        hostname = socket.gethostname()
        cfg['unitRef']='unit' + hostname[-2:]
        cfg['raw_data_dir']='/media/nvme/RawDataLocal'
        cfg['compressed_video_dir']='/home/wrw/Documents/RawDataLocal'
        cfg['COM']='/dev/ttyACM0'
        cfg['axesRef']='cam0'
        cfg['pelletXY']= [0, 0]
        cfg['roiXWYH']= [0, 30, 0, 100]
        cfg['stimAxes']='cam0'
        cfg['stimXWYH']= [0, 30, 0, 100]
        cfg['stimRate']=600
        write_config(cfg)
    return(cfg)

def write_config(cfg):
    """
    Write structured config file.
    """
    usrdatadir = os.path.dirname(os.path.realpath(__file__))
    configname = os.path.join(usrdatadir, 'userdata.yaml')
    
    with open(configname, 'w') as cf:
        ruamelFile = ruamel.yaml.YAML()
        cfg_file,ruamelFile = cam_config_template()
        for key in cfg.keys():
            cfg_file[key]=cfg[key]
        
        ruamelFile.dump(cfg_file, cf)
        
def metadata_template():
    """
    Creates a template for config.yaml file. This specific order is preserved while saving as yaml file.
    """
    yaml_str = """\
# Cameras
    cam1:
    cam2:
    cam3:
    cam4:
    \n

# Mouse
    ID:
    placeholderA:
    placeholderB:
    \n

# Experiment
    Designer:
    Stim:
    StartTime:
    Collection:
    \n

# Stim ROI
    stimAxes:
    stimXWYH:
    \n

# Pellet and ROI
    axesRef:
    pelletXY:
    roiXWYH:
    \n
    """
    
    ruamelFile = ruamel.yaml.YAML()
    cfg_file = ruamelFile.load(yaml_str)
    return cfg_file, ruamelFile

def read_metadata(path):
    ruamelFile = ruamel.yaml.YAML()
    if os.path.exists(path):
        with open(path, 'r') as f:
            cfg = ruamelFile.load(f)
    return(cfg)

def write_metadata(cfg, path):
    with open(path, 'w') as cf:
        ruamelFile = ruamel.yaml.YAML()
        cfg_file,ruamelFile = cam_config_template()
        for key in cfg.keys():
            cfg_file[key]=cfg[key]
        ruamelFile.dump(cfg_file, cf)
