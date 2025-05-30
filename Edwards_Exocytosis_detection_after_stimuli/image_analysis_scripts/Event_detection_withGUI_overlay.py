import sys, os
import math

from ij import IJ, WindowManager, ImagePlus
from ij.io import DirectoryChooser, FileSaver
from ij.gui import WaitForUserDialog, GenericDialog
from ij.plugin import ImageCalculator, PlugIn
from ij.measure import Measurements, ResultsTable
from ij.plugin.frame import RoiManager
from ij.text import TextWindow

from fiji.plugin.trackmate import Model, Settings, TrackMate, SelectionModel, Logger, Spot, SpotCollection
from fiji.plugin.trackmate.detection import LogDetectorFactory
from fiji.plugin.trackmate.tracking.jaqaman import SparseLAPTrackerFactory
from fiji.plugin.trackmate.action import ExportAllSpotsStatsAction, LabelImgExporter, CaptureOverlayAction
from fiji.plugin.trackmate.gui.displaysettings import DisplaySettings, DisplaySettingsIO
import fiji.plugin.trackmate.visualization.hyperstack.HyperStackDisplayer as HyperStackDisplayer
from fiji.plugin.trackmate.providers import SpotAnalyzerProvider, EdgeAnalyzerProvider, TrackAnalyzerProvider
from fiji.plugin.trackmate.action.LabelImgExporter.LabelIdPainting import LABEL_IS_INDEX

dc=DirectoryChooser("Choose a folder")
input_dir=dc.getDirectory() #folder were all time-lapse images are saved
if input_dir is None:
    print("User Canceled")

else:
  gd=GenericDialog(input_dir)
  gd.addRadioButtonGroup("Are files on tiff format?", ["Yes", "No"], 1, 2, "Yes")
  gd.addStringField("if not, what format?", "tif", 5)
  gd.addNumericField("Number of frames", 100, 0,)
  gd.addNumericField("Number of stimuli",8,0)
  gd.addNumericField("First stimuli frame",20,0)
  gd.addNumericField("Stimuli frame interval",6,0)
  gd.addNumericField("Number of frames on NH3 movie",26,0)
  gd.addNumericField("NH3 addition frame",22,0)
  gd.addNumericField("Spot diameter",5,2)
  gd.addNumericField("Threshold",100,1)
  gd.addNumericField("Link distance",2,1)
  gd.addNumericField("Gap distance",2,1)
  gd.addStringField("Output folder", "output_path", 60)
  gd.showDialog()  
  if gd.wasCanceled():
    print("User canceled dialog!")
  else:
 #settings for image processing to improve signal/noise ratio
    is_tiff = gd.getNextRadioButton()
    file_type = gd.getNextString()
    frames = int(gd.getNextNumber()) #length of time-lapse movie
    stimuli = int(gd.getNextNumber()) #number of stimuli
    first_stimuli = int(gd.getNextNumber()) #frame where first stimuli is given
    step_size = int(gd.getNextNumber()) #rate of stimuli
    NH3_frames = int(gd.getNextNumber()) #length of NH3 time-lapse movie
    total_frame = int(gd.getNextNumber()) #frame NH3 was added 
    diameter = float(gd.getNextNumber())
    threshold = float(gd.getNextNumber()) #threshold for the event detection larger values will result in less events detected, bright events being detected,
                #smaller values will result in more event but this might include false events
    link_distance = int(gd.getNextNumber()) #this set the distance that an event can whitin a frame for static events this value should be set close to 0
    gap_distance = int(gd.getNextNumber()) #this set the distance that an event can move from frame to frame, for static events this value should be set close to 0\
    output_dir=gd.getNextString() #folder were files created will be saved
    

ic =  ImageCalculator();
#reload(sys)
#sys.setdefaultencoding('utf-8')


#Process each movie and return a label image with each event as a spot numbered based on the trackId as well as a .csv table with x,y and frame position for each event and the track it belongs too

movies = os.listdir(input_dir)
print (movies)
for eachobj in movies:
	name = eachobj.split(".")[0]
	subname = "NH3"
	if subname in name:
		name = eachobj.split("_")[0]
		if is_tiff=="No":
			IJ.run("Bio-Formats Windowless Importer","open="+os.path.join(input_dir,eachobj));
			IJ.saveAs("Tiff",os.path.join(output_dir,name+'.tif'));
		else:
			imp = IJ.run("Bio-Formats Windowless Importer","open="+os.path.join(input_dir,eachobj));
		
#how the total movie is processed
		h = NH3_frames
		j = total_frame
		i = j - 1
		k = j + 1
		l = h - j 
		IJ.selectWindow(str(name)+"_NH3.tif");
		IJ.run("Make Substack...", "slices="+str(i));
		IJ.selectWindow(str(name)+"_NH3.tif");
		IJ.run("Make Substack...", "slices="+str(k)+"-"+str(h));
		imp1= WindowManager.getImage("Substack ("+ str(k)+"-"+str(h)+")");
		imp2= WindowManager.getImage("Substack ("+ str(i)+")");
		imp = ImageCalculator.run(imp1, imp2, "Subtract create stack");
		imp.show()
		imp.setTitle("img_for_TM");
		IJ.selectWindow("Substack ("+ str(i)+")");
		IJ.run ("Close");
		IJ.selectWindow("Substack ("+ str(k)+"-"+ str(h)+")");
		
	#Trackmate model, detector, tracking and export of spots and tracks
		model = Model()
		settings = Settings(imp)
		radius = float(diameter)/2
	
		settings.detectorFactory = LogDetectorFactory()
		settings.detectorSettings = {
			'DO_SUBPIXEL_LOCALIZATION' : False,
			'RADIUS' : float(radius),
			'TARGET_CHANNEL' : 1,
			'THRESHOLD' : float(threshold),
			'DO_MEDIAN_FILTERING' : False,
			}
	
		settings.trackerFactory = SparseLAPTrackerFactory()
		settings.trackerSettings = settings.trackerFactory.getDefaultSettings()
		settings.trackerSettings['LINKING_MAX_DISTANCE'] = float(link_distance)
		settings.trackerSettings['GAP_CLOSING_MAX_DISTANCE'] = float(gap_distance)
		settings.trackerSettings['MAX_FRAME_GAP'] = 0
		trackmate = TrackMate(model, settings)
	
		ok = trackmate.checkInput()
		if not ok:
			sys.exit(str(trackmate.getErrorMessage()))
	
		ok = trackmate.process()
		if not ok:
			sys.exit(str(trackmate.getErrorMessage()))
	
		selectionModel = SelectionModel(model)
	
		exportSpotsAsDots = False
		exportTracksOnly = True
		lblImg = LabelImgExporter.createLabelImagePlus(trackmate, exportSpotsAsDots, exportTracksOnly, LABEL_IS_INDEX)
		lblImg.show()
		IJ.selectWindow('LblImg_img_for_TM');
		IJ.saveAs("Tiff",os.path.join(output_dir,name+'_NH3_lblImg.tif'));
		
		ds = DisplaySettingsIO.readUserDefault()
	
		fm = model.getFeatureModel()
	
		rt_exist = WindowManager.getWindow("TrackMate Results")
	
		if rt_exist==None or not isinstance(rt_exist, TextWindow):
			table= ResultsTable()
		else:
			table = rt_exist.getTextPanel().getOrCreateResultsTable()
		table.reset()
	
		for id in model.getTrackModel().trackIDs(True):
			v = fm.getTrackFeature(id, 'TRACK_MEAN_SPEED')
			model.getLogger().log('')
			model.getLogger().log('Track ' + str(id) + ': mean velocity = ' + str(v) + ' ' + model.getSpaceUnits() + '/' + model.getTimeUnits())
			track = model.getTrackModel().trackSpots(id)
	
			for spot in track:
				sid = spot.ID()
				x=spot.getFeature('POSITION_X')
				y=spot.getFeature('POSITION_Y')
				t=spot.getFeature('FRAME')
				q=spot.getFeature('QUALITY')
				snr=spot.getFeature('SNR')
				mean=spot.getFeature('MEAN_INTENSITY')
				model.getLogger().log('\tspot ID = ' + str(sid) + ': x='+str(x)+', y='+str(y)+', t='+str(t)+', q='+str(q))
				table.incrementCounter()
				table.addValue("TRACK_ID", id)
				table.addValue("SPOT_ID", sid)
				table.addValue("POSITION_X", x)
				table.addValue("POSITION_Y", y)
				table.addValue("FRAME", t)
				table.addValue("QUALITY", q)
		table.show("TrackMate Results")
		IJ.selectWindow('TrackMate Results');
		IJ.saveAs("Measurements",os.path.join(output_dir,name+'_total.csv'));
		IJ.selectWindow(name+'_total.csv');
		IJ.run ("Close");
		imp1.setTitle("Original");
		IJ.selectWindow(name+'_lblImg_NH3.tif');
		IJ.run("Make Substack...", "slices=1-"+str(l));
		IJ.run("Multiply...", "value=10 stack");
		IJ.run("Manual Threshold", "min=0 max=1");
		IJ.run("Make Binary", "method=Default background=Default");
		IJ.run("Outline", "stack");
		IJ.run("16-bit", "");
		img4= WindowManager.getImage("Substack (1-"+str(l)+")");
		img4.setTitle("MASK_Events");
		IJ.run("Merge Channels...", "c1=MASK_Events c4=Original create keep ignore");
		IJ.saveAs("Tiff",os.path.join(output_dir, name + "_NH3_overlay.tif"));
		IJ.run ("Close All");
		
#how the original movie is processed		
	elif subname not in name:
		if is_tiff=="No":
			IJ.run("Bio-Formats Windowless Importer","open="+os.path.join(input_dir,eachobj));
			IJ.saveAs("Tiff",os.path.join(output_dir,name+'.tif'));
		else:
			imp = IJ.run("Bio-Formats Windowless Importer","open="+os.path.join(input_dir,eachobj));
			
##image processing to improve spot detection
	
		for i in range (0, stimuli):
			j = first_stimuli + (i*step_size)
			k = j + step_size
			l = i + 1
			IJ.selectWindow(str(name)+".tif");
			IJ.run("Make Substack...", "slices=" + str(j)+ "-"+str(k));
			IJ.selectWindow("Substack ("+ str(j)+ "-"+str(k)+")");
			IJ.run("Make Subset...", "slices=1 delete");
			img1= WindowManager.getImage("Substack ("+ str(j)+ "-"+str(k)+")");
			img2= WindowManager.getImage("Substack (1)");
			imp = ImageCalculator.run(img1, img2, "Subtract create stack");
			imp.show();
			imp.setTitle("img"+str(i));
			IJ.selectWindow("Substack ("+ str(j)+ "-"+str(k)+")");
			IJ.run ("Close");
			IJ.selectWindow("Substack (1)");
			IJ.run ("Close");
			
			
			model = Model()
			settings = Settings(imp)
			radius = float(diameter)/2
		
			settings.detectorFactory = LogDetectorFactory()
			settings.detectorSettings = {
				'DO_SUBPIXEL_LOCALIZATION' : False,
				'RADIUS' : float(radius),
				'TARGET_CHANNEL' : 1,
				'THRESHOLD' : float(threshold),
				'DO_MEDIAN_FILTERING' : False,
				}
		
			settings.trackerFactory = SparseLAPTrackerFactory()
			settings.trackerSettings = settings.trackerFactory.getDefaultSettings()
			settings.trackerSettings['LINKING_MAX_DISTANCE'] = float(link_distance)
			settings.trackerSettings['GAP_CLOSING_MAX_DISTANCE'] = float(gap_distance)
			settings.trackerSettings['MAX_FRAME_GAP'] = 0
			trackmate = TrackMate(model, settings)
		
			ok = trackmate.checkInput()
			if not ok:
				sys.exit(str(trackmate.getErrorMessage()))
		
			ok = trackmate.process()
			if not ok:
				sys.exit(str(trackmate.getErrorMessage()))
		
			selectionModel = SelectionModel(model)
			
			exportSpotsAsDots = False
			exportTracksOnly = True
			
			ds = DisplaySettingsIO.readUserDefault()
		
			fm = model.getFeatureModel()
		
			rt_exist = WindowManager.getWindow("TrackMate Results")
		
			if rt_exist==None or not isinstance(rt_exist, TextWindow):
				table= ResultsTable()
			else:
				table = rt_exist.getTextPanel().getOrCreateResultsTable()
			table.reset
		
			for id in model.getTrackModel().trackIDs(True):
				v = fm.getTrackFeature(id, 'TRACK_MEAN_SPEED')
				model.getLogger().log('')
				model.getLogger().log('Track ' + str(id) + ': mean velocity = ' + str(v) + ' ' + model.getSpaceUnits() + '/' + model.getTimeUnits())
				track = model.getTrackModel().trackSpots(id)
		
				for spot in track:
					sid = spot.ID()
					x=spot.getFeature('POSITION_X')
					y=spot.getFeature('POSITION_Y')
					t=spot.getFeature('FRAME')
					q=spot.getFeature('QUALITY')
					snr=spot.getFeature('SNR')
					mean=spot.getFeature('MEAN_INTENSITY')
					model.getLogger().log('\tspot ID = ' + str(sid) + ': x='+str(x)+', y='+str(y)+', t='+str(t)+', q='+str(q))
					table.incrementCounter()
					table.addValue("TRACK_ID", id)
					table.addValue("SPOT_ID", sid)
					table.addValue("POSITION_X", x)
					table.addValue("POSITION_Y", y)
					table.addValue("FRAME", t)
					table.addValue("QUALITY", q)
			table.show("TrackMate Results")
			IJ.selectWindow('TrackMate Results');
			IJ.saveAs("Measurements",os.path.join(output_dir,name+'_img'+str(l)+'.csv'));
			IJ.selectWindow(name+'_img'+str(l)+'.csv');
			IJ.run ("Close");
			
		j = first_stimuli
		k = frames
		l = k - j
		IJ.selectWindow(str(name)+".tif");
		IJ.run("Make Substack...", "slices="+str(j)+"-"+str(k));
		IJ.selectWindow("Substack ("+str(j)+"-"+str(k)+")");
		IJ.run("Make Subset...", "slices=1 delete");
		img1= WindowManager.getImage("Substack ("+ str(j)+"-"+str(k)+")");
		img2= WindowManager.getImage("Substack (1)");	
		imp = ImageCalculator.run(img1, img2, "Subtract create stack");
		imp.show();
		imp.setTitle("img_for_TM");
		IJ.selectWindow("Substack (1)");
		IJ.run ("Close");
	
	#Trackmate model, detector, tracking and export of spots and tracks
		model = Model()
		logger = model.getLogger()
		settings = Settings(imp)
		radius = float(diameter)/2
	
		settings.detectorFactory = LogDetectorFactory()
		settings.detectorSettings = {
			'DO_SUBPIXEL_LOCALIZATION' : False,
			'RADIUS' : float(radius),
			'TARGET_CHANNEL' : 1,
			'THRESHOLD' : float(threshold),
			'DO_MEDIAN_FILTERING' : False,
			}
	
		settings.trackerFactory = SparseLAPTrackerFactory()
		settings.trackerSettings = settings.trackerFactory.getDefaultSettings()
		settings.trackerSettings['LINKING_MAX_DISTANCE'] = float(link_distance)
		settings.trackerSettings['GAP_CLOSING_MAX_DISTANCE'] = float(gap_distance)
		settings.trackerSettings['MAX_FRAME_GAP'] = 0
		trackmate = TrackMate(model, settings)
	
		ok = trackmate.checkInput()
		if not ok:
			sys.exit(str(trackmate.getErrorMessage()))
	
		ok = trackmate.process()
		if not ok:
			sys.exit(str(trackmate.getErrorMessage()))
	
		selectionModel = SelectionModel(model)
		
		exportSpotsAsDots = False
		exportTracksOnly = True
		lblImg = LabelImgExporter.createLabelImagePlus( trackmate, exportSpotsAsDots, exportTracksOnly, LABEL_IS_INDEX)
		lblImg.setTitle("EventsLabel")
		lblImg.show()
		lblImg.show()
		IJ.selectWindow('EventsLabel');
		IJ.saveAs("Tiff",os.path.join(output_dir,name+'_lblImg.tif'));
	
		ds = DisplaySettingsIO.readUserDefault()
	
		fm = model.getFeatureModel()
	
		rt_exist = WindowManager.getWindow("TrackMate Results")
	
		if rt_exist==None or not isinstance(rt_exist, TextWindow):
			table= ResultsTable()
		else:
			table = rt_exist.getTextPanel().getOrCreateResultsTable()
		table.reset
	
		for id in model.getTrackModel().trackIDs(True):
			v = fm.getTrackFeature(id, 'TRACK_MEAN_SPEED')
			model.getLogger().log('')
			model.getLogger().log('Track ' + str(id) + ': mean velocity = ' + str(v) + ' ' + model.getSpaceUnits() + '/' + model.getTimeUnits())
			track = model.getTrackModel().trackSpots(id)
	
			for spot in track:
				sid = spot.ID()
				x=spot.getFeature('POSITION_X')
				y=spot.getFeature('POSITION_Y')
				t=spot.getFeature('FRAME')
				q=spot.getFeature('QUALITY')
				snr=spot.getFeature('SNR')
				mean=spot.getFeature('MEAN_INTENSITY')
				model.getLogger().log('\tspot ID = ' + str(sid) + ': x='+str(x)+', y='+str(y)+', t='+str(t)+', q='+str(q))
				table.incrementCounter()
				table.addValue("TRACK_ID", id)
				table.addValue("SPOT_ID", sid)
				table.addValue("POSITION_X", x)
				table.addValue("POSITION_Y", y)
				table.addValue("FRAME", t)
				table.addValue("QUALITY", q)
		table.show("TrackMate Results")
		IJ.selectWindow("TrackMate Results");
		IJ.saveAs("Measurements",os.path.join(output_dir,name+'_whole.csv'));
		IJ.selectWindow(name+'_whole.csv');
		IJ.run ("Close");
		img1.setTitle("Original")
		IJ.selectWindow(name+'_lblImg.tif');
		IJ.run("Make Substack...", "slices=1-"+str(l));
		IJ.run("Multiply...", "value=10 stack");
		IJ.run("Manual Threshold", "min=0 max=1");
		IJ.run("Make Binary", "method=Default background=Default");
		IJ.run("Outline", "stack");
		IJ.run("16-bit", "");
		img4= WindowManager.getImage("Substack (1-"+str(l)+")");
		img4.setTitle("MASK_Events")
		IJ.run("Merge Channels...", "c1=MASK_Events c4=Original create keep ignore");
		IJ.saveAs("Tiff",os.path.join(output_dir, name + "_overlay.tif"))
		IJ.run ("Close");
		IJ.run("Close All");
	