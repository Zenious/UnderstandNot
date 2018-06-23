from sanic import Sanic
from sanic import response
from extractAudio import AudioExtract
from readJSON import Transcribe
import uuid 
import boto3
import urllib

app = Sanic()
app.config.REQUEST_MAX_SIZE = 1000000000 # 1GB
app.static('/static', '.')

# dynamodb = boto3.resource('dynamodb', region_name='us-west-2', endpoint_url="http://localhost:8001")

@app.route('/')
async def test(request):
    return response.html('''<!doctype html>
    <title>Upload new File</title>
    <h1>Upload new File</h1>
    <form action="upload" method=post enctype=multipart/form-data>
      <input type=file name=file accept="video/*">
      <input type=submit value=Upload>
    </form>   
    <h1>Upload new JSON</h1>
    <form action="parse" method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
        ''')


@app.route('/upload', methods=['POST'])
async def post_upload(request):
    if 'file' not in request.files:
        return response.text('no files')
    file = request.files['file']
    file_body = file[0].body
    file_name = file[0].name
    file_type = file[0].type

    # check if is valid filetype
    if 'video' in file_type:
        # generate db record for index
        index =  uuid.uuid4().hex
        # table = dynamodb.Table('Videos')
        # table.put_item(Item={
        #     'id': index,
        #     'title': file_name
        #     } )

        create_file(index, file_body)
        # TODO upload video to S3 Bucket
        audio_file = AudioExtract.extractFLAC(index)
        # TODO upload audio to S3 Bucket
        bucket = 'orbitalphase1'
        s3 = boto3.client('s3')
        s3.upload_file(audio_file, bucket, audio_file)
        # TODO send req to transcribe
        transcribe = boto3.client('transcribe')

        result = transcribe.start_transcription_job(
            TranscriptionJobName=index,
            LanguageCode='en-US',
            MediaSampleRateHertz=44100,
            MediaFormat='flac',
            Media={
                'MediaFileUri': 'https://s3-us-east-2.amazonaws.com/{}/{}'.format(bucket,audio_file)
            }
        )
        return response.redirect('/job/{}'.format(index))

    else:
        create_file(file_name, file_body)
        trans = Transcribe()
        trans.parseOutput(file_name)
        return response.text(file_type)

def create_file(filename, data):
    f = open(filename, 'wb')
    f.write(data)
    f.close()

@app.route('/parse', methods=['POST'])
async def post_transcribe(request):
    Transcribe.parseOutput()
    return response.text("TODO")

@app.route('/job/<id>')
async def retrieve_job(request, id):
    transcribe = boto3.client('transcribe')
    result = transcribe.get_transcription_job(
        TranscriptionJobName=id)

    status = result['TranscriptionJob']['TranscriptionJobStatus']

    if status == 'COMPLETED':
        trans_uri = result['TranscriptionJob']['Transcript']['TranscriptFileUri']
        trans_file = 'trans{}'.format(id)
        urllib.request.urlretrieve(trans_uri,trans_file)
        trans = Transcribe()
        trans.parseOutput(trans_file)

    return response.html('''<!DOCTYPE html>
<html>
<body>
STATUS : {}
<audio controls>
  <source src="/static/{}" type="audio/flac">
Your browser does not support the audio element.
</audio>

<a href="/static/trans{}.srt">DOWNLOAD LINK</a>
</body>
</html>

            '''.format(status,id, id))



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)