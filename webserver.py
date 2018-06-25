from sanic import Sanic
from sanic import response
import uuid 
import boto3
import urllib
from redis import Redis
from rq import Queue
from rq_worker import aws_stuff
from sanic_jinja2 import SanicJinja2
from readJSON import Transcribe
from hashlib import md5
import json

app = Sanic()
app.config.REQUEST_MAX_SIZE = 1000000000 # 1GB
app.static('/static', '.')

jinja = SanicJinja2(app)
redis_connection = Redis()
q = Queue(connection=redis_connection)
dynamodb = boto3.resource('dynamodb')


@app.route('/')
@jinja.template('index.html')
async def test(request):
    return 


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
        index =  uuid.uuid4().hex
        create_file(index, file_body)
        hashcode = compute_md5(file_body)
        table = dynamodb.Table('Videos')
        table.put_item(Item={
            'id': index,
            'title': file_name,
            'hash': hashcode,
            'job_status': 'Queue for Audio Extraction',
            'transcript': None,
            'subs': None
            } )

        q.enqueue(aws_stuff, index)
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

def compute_md5(data):
    m = md5()
    m.update(data)
    return m.digest()

@app.route('/parse', methods=['POST'])
async def post_transcribe(request):
    Transcribe.parseOutput()
    return response.text("TODO")

@app.route('/job/<id>')
@jinja.template('job.html')
async def retrieve_job(request, id):
    table = dynamodb.Table('Videos')
    db_query = table.get_item(
        Key={'id':id},
        ConsistentRead=True
        )
    db_item = db_query['Item']
    job_status = db_item['job_status']

    if job_status == 'Sent Audio For Transcription':
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
            table = dynamodb.Table('Videos')
            trans_data = {}
            with open(trans_file, "r") as f:
                trans_data = json.load(f)
            table.update_item(
                Key= {'id': id},
                UpdateExpression = "SET job_status=:job_status, transcript=:transcript",
                ExpressionAttributeValues={
                    ':job_status': 'Transcription done',
                    ':transcript': trans_data
                    }
                )
            return {
            'status': status,
            'srt': trans_file,
            'flac': id
            }
        else: 
            return {
            'status': status
            }

    elif job_status == 'Transcription done':

        return  {
        'status': job_status,
        'flac': id,
        'srt': 'trans{}'.format(id)
        }

    else:
        return {
        'status': job_status,
        }
       

@app.route('/video/<id>')
@jinja.template('video.html')
async def video(request, id):
    t = Transcribe()
    srt_filename = 'trans{}.srt'.format(id)
    t.srt_to_vtt(srt_filename)
    return {
    'vtt': srt_filename,
    'id': id
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, workers=10)