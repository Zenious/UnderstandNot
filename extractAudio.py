#!/root/anaconda3/bin/python

import ffmpeg

# Extract Audio from Video

input_video = ffmpeg.input("UnderstandNot (1).mp4")
output_audio = input_video.output('UDS.flac', ac='2', ab='160k', ar='44100')
output_audio.run()
