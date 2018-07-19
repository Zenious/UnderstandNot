import ffmpeg
import os

# Extract Audio from Video
# def run():
# 	input_video = ffmpeg.input("UnderstandNot (1).mp4")
# 	output_audio = input_video.output('UDS.flac', ac='2', ab='160k', ar='44100')
# 	output_audio.run()

class AudioExtract:
	def extractFLAC(filename):
		base = os.path.basename(filename)
		basename = os.path.split(base)[0]
		if basename == "":
			basename = filename
		flacname = './resources/' + basename + ".flac"
		input_video = ffmpeg.input('./resources/{}'.format(filename))
		output_audio = input_video.output(flacname, ac='1', ab='64k', ar='44100')
		output_audio.run()
		return flacname
