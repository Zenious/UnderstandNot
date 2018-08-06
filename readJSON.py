import json
import sys
import re
import io

RGX_TIMESTAMP_MAGNITUDE_DELIM = r'[,.:]'
RGX_TIMESTAMP = RGX_TIMESTAMP_MAGNITUDE_DELIM.join([r'\d+'] * 4)
RGX_INDEX = r'\d+'
RGX_PROPRIETARY = r'[^\r\n]*'
RGX_CONTENT = r'.*?'
RGX_POSSIBLE_CRLF = r'\r?\n'

SRT_REGEX = re.compile(
        r'({idx})\s*{eof}({ts}) --> ({ts}) ?({proprietary}){eof}({content})'
        r'(?:{eof}|\Z)(?:{eof}|\Z|(?=(?:{idx}\s*{eof}{ts})))'
        r'(?=(?:{idx}\s*{eof}{ts}|\Z))'.format(
            idx=RGX_INDEX,
            ts=RGX_TIMESTAMP,
            proprietary=RGX_PROPRIETARY,
            content=RGX_CONTENT,
            eof=RGX_POSSIBLE_CRLF,
            ),
        re.DOTALL,
        )

class Transcribe:

    def __init__(self):
        self.TIMING = 1

    def formatTiming(self, x): 
        time_str = str(x)
        time_str = time_str.split('.')
        minute,sec = divmod(int(time_str[0]),60)
        hour, minute = divmod(minute, 60)
        time_str[0] = sec
        time_str.insert(0, minute)
        time_str.insert(0, hour)
        str_format = '{:02}:{:02}:{:02},{:0<3}'.format(time_str[0], time_str[1], time_str[2], time_str[3])
        return str_format

    def parseOutput(self, json_file):
        sentence = ''
        building_block = []
        current_time = 0.0
        time_sector = 1
        captions = []
        data = {}
        timing_block = []

        with open(json_file,'r') as f:
            data = json.load(f)

        for block in data['results']['items']:
            if 'end_time' in block:
                end_time = float(block['end_time'])
                if end_time > time_sector * self.TIMING:
                    sentence = ' '.join(building_block)
                    building_block = []
                    output = (current_time, end_time, sentence)
                    captions.append(output)
                    current_time = block['end_time']
                    time_sector = end_time/1 + 1
            word = block['alternatives'][0]['content']
            if block['type'] == 'punctuation':
                building_block[-1] = building_block[-1] + word
            else: 
                building_block.append(word)

        sentence = ' '.join(building_block)
        output = (current_time, end_time, sentence)
        captions.append(output)

        srt_file = json_file + '.srt'
        with open(srt_file, 'w') as f:
            for x,y in enumerate(captions):
                print(x+1, file=f)
                str_format = '{} --> {}'.format(self.formatTiming(y[0]), self.formatTiming(y[1]))
                print (str_format, file=f)
                print (y[2], file=f)
                print('',file=f)

    def srt_to_vtt(self, srt_file):
        vtt_file = srt_file + '.vtt'
        with open(vtt_file, 'w') as f:
            print ('WEBVTT', file=f)
            print('', file=f)
            with open(srt_file, 'r') as srt:
                lines = srt.readlines()
                for line in lines:
                    line = re.sub(r'(\d{2}),(\d{3})',r'\1.\2', line)
                    f.write(line)

    def srt_to_vtt_mem(self, srt_file):
        output = io.StringIO()
        output.write('WEBVTT\n')
        output.write('\n')
        with open("resources/{}".format(srt_file), 'r') as srt:
            lines = srt.readlines()
            for line in lines:
                line = re.sub(r'(\d{2}),(\d{3})',r'\1.\2', line)
                output.write(line)	
        text = output.getvalue()
        output.close()
        return text

    def srt_mem_to_vtt_mem(self, srt_mem):
        output = io.StringIO()
        output.write('WEBVTT\n')
        output.write('\n')
        lines = srt_mem.split('\n')
        for line in lines:
            line = re.sub(r'(\d{2}),(\d{3})',r'\1.\2', line)
            output.write(line+"\n")	
        text = output.getvalue()
        output.close()
        return text

    def srt_mem(self, srt_file):
        output = io.StringIO()
        with open("{}".format(srt_file), 'r') as srt:
            lines = srt.readlines()
            for line in lines:
                output.write(line)	
        text = output.getvalue()
        output.close()
        return text

    def vtt_mem_to_srt(self, vtt_mem):
        output = io.StringIO()
        lines = vtt_mem.split('\n')
        lines = lines[2:] 
        for line in lines:
            line = re.sub(r'(\d{2}).(\d{3})',r'\1,\2', line)
            output.write(line+'\n')

        return output.getvalue()

    def parse_to_edit(self, trans):
        sentence = ''
        building_block = []
        current_time = 0.0
        time_sector = 1
        captions = []
        timing_block = []
        #print(trans)
        for block in trans['results']['items']:
            if 'end_time' in block:
                end_time = float(block['end_time'])
                if end_time > time_sector * self.TIMING:
                    sentence = ' '.join(building_block)
                    building_block = []
                    output = {'start':current_time, 
                            'end': end_time, 
                            'text': sentence
                            }
                    captions.append(output)
                    current_time = block['end_time']
                    time_sector = end_time/1 + 1
            word = block['alternatives'][0]['content']
            if block['type'] == 'punctuation':
                building_block[-1] = building_block[-1] + word
            else: 
                building_block.append(word)

        sentence = ' '.join(building_block)
        output = {'start':current_time, 
                'end': end_time, 
                'text': sentence
                }
        captions.append(output)
        return captions

    def srt_to_edit(self, srt):
        captions = []
        for match in SRT_REGEX.finditer(srt):
            index, start_time, end_time, proprietary, text = match.groups()
            #print("Start: {}| End: {}| Text: {}".format(raw_start, raw_end, content))
            output = {'start': start_time, 
                    'end': end_time, 
                    'text': text
                    }
            captions.append(output)

        return captions

    def make_change_vtt(self, vtt, index, start, end, text):
        vtt_list = vtt.split('\n')
        #TODO check the format if correct
        timing = "{} --> {}".format(start, end)
        #timing = "{} --> {}".format(formatTiming(start), formatTiming(end)
        timing = re.sub(r'(\d{2}),(\d{3})',r'\1.\2', timing)
        vtt_list[(index)*4-1] = timing
        vtt_list[(index)*4] = text
        new_vtt = "\n".join(vtt_list)
        return new_vtt
