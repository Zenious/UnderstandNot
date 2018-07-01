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
from boto3.dynamodb.conditions import Attr
from functools import reduce

app = Sanic()
app.config.REQUEST_MAX_SIZE = 1000000000 # 1GB
app.static('/static', '.')

jinja = SanicJinja2(app)
redis_connection = Redis()
q = Queue(connection=redis_connection)
dynamodb = boto3.resource('dynamodb')


@app.route('/')
@jinja.template('index.html')
async def index(request):
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

        #TODO check duplicates

        table = dynamodb.Table('Videos')
        table.put_item(Item={
            'id': index,
            'title': file_name,
            'hash': hashcode,
            'job_status': 'Queue for Audio Extraction',
            'transcript': None,
            'subs': None,
            'count': 0
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

@app.route('/search')
async def search_redirect(request):
    inputs = request.args
    return response.redirect('/search/{}'.format(inputs['search'][0]))


@app.route('/search/<title>')
@jinja.template('search.html')
async def search(request, title):
    # get GET Parameters
    table = dynamodb.Table('Videos')
    db_query = table.scan(
        FilterExpression=Attr('title').contains(title),
        ConsistentRead=True
        )
    items = db_query['Items']
    # titles = reduce((lambda x: x['title']) , items, [])
    extract_title = lambda x:x['title']
    extract_id = lambda x:x['id']
    results = []
    for item in items:
        info = {}
        info.update({'title': extract_title(item)})
        info.update({'id' : extract_id(item)})
        results.append(info)
    return {'results': results}


@app.route('/job/<id>')
@jinja.template('job.html')
async def retrieve_job(request, id):
    jinja_response = {}

    table = dynamodb.Table('Videos')
    db_query = table.get_item(
        Key={'id':id},
        ConsistentRead=True
        )
    db_item = db_query['Item']
    job_status = db_item['job_status']
    title = {'title': db_item['title']}
    jinja_response.update(title)
    if job_status == 'Sent Audio For Transcription':
        transcribe = boto3.client('transcribe')
        result = transcribe.get_transcription_job(
            TranscriptionJobName=id)

        status = result['TranscriptionJob']['TranscriptionJobStatus']
        jinja_response.update({'status': status})
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
            jinja_response.update({'srt': trans_file, 'flac': id, 'ready': True})
            return jinja_response
        else: 
            return jinja_response
    elif job_status == 'Transcription done':
        jinja_response.update({
            'flac': id,
            'srt': 'trans{}'.format(id),
            'ready': True
            })
        return jinja_response
    else:
        return jinja_response
       

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

@app.route('/vote')
async def vote(request):
    args = request.args
    query_id = args.get('id')
    query_vote = args.get('vote')

    table = dynamodb.Table('Videos')
    db_query = table.get_item(
        Key={'id':query_id},
        ConsistentRead=True
    )
    item = db_query['Item']
    count = item['count']
    if count is None:
        count = 0
    if query_vote == 'yes':
        count += 1
    else:
        count -= 1
    table.update_item(
        Key= {'id': id},
        UpdateExpression = "SET vote=:count",
        ExpressionAttributeValues={
            ':count': count
            }
    )
    return response.json({'status': 'ok', 'count': count})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, workers=10)